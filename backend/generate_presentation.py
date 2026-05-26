from __future__ import annotations

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any

from llmai.shared.messages import SystemMessage, UserMessage
from llmai.shared.response_formats import JSONSchemaResponse

from generation_schema import create_layouts_generation_schemas
from llm_models import SlideLayouts
from template import (
    DEFAULT_MODEL,
    _create_openrouter_client,
    _openrouter_extra_body,
    _parse_json_content,
)


ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_LAYOUTS_FILE = ASSETS_DIR / "layouts.json"
DEFAULT_SCHEMAS_FILE = ASSETS_DIR / "schemas.json"
DEFAULT_OUTPUT_FILE = ASSETS_DIR / "generated_presentation.json"
DEFAULT_PROMPT = "Create a coherent replacement presentation using the provided layout."

OUTLINE_GENERATION_PROMPT = """
Create slide-by-slide content for a new presentation.
The user prompt contains the presentation request and the available slide layouts.

# Steps
1. Read the presentation request and layout descriptions.
2. Create one slide content plan for every layout.
3. Return the slide plans in the same order as the layouts.

# Content Rules
- Make the slides work together as one coherent presentation.
- Use each layout according to its description and available fields.
- Keep each slide focused on a distinct part of the requested presentation.
- Include concrete content direction, not generic placeholders.
- Include visual direction for images, charts, tables, repeated items, and other media when relevant.

# Output Rules
- Return raw JSON only matching the provided schema.
- Do not include markdown fences, comments, explanations, or any text before or after the JSON object.
"""

CONTENT_GENERATION_PROMPT = """
Generate new slide content for one existing slide layout.
The user prompt contains the presentation request, one slide content plan, layout metadata, and the required JSON schema.

# Steps
1. Read the slide content plan and field schema.
2. Generate replacement content for every required field.
3. Return one JSON object matching the provided schema.

# Content Rules
- Follow the slide content plan closely.
- Keep all content suitable for the existing layout and component descriptions.
- Preserve the purpose and approximate length of each placeholder.
- Return values only for the fields defined by the schema.
- For image fields, return a precise image `prompt` and a short `name`.
- For table fields, return column and row text that fits the existing table structure.
- For chart fields, return realistic labels and numeric values.
- For repeated item fields, return a complete array of items within the schema bounds.

# Output Rules
- Return raw JSON only matching the provided schema.
- Do not include markdown fences, comments, explanations, or any text before or after the JSON object.
"""

PATH_PART_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)])?$")
ELEMENT_TYPES = {
    "chart",
    "container",
    "ellipse",
    "flex",
    "grid",
    "grid-view",
    "image",
    "line",
    "list-view",
    "rectangle",
    "stack",
    "table",
    "text",
    "text-list",
}


def generate_presentation(
    *,
    layouts_file: Path = DEFAULT_LAYOUTS_FILE,
    schemas_file: Path = DEFAULT_SCHEMAS_FILE,
    output_file: Path = DEFAULT_OUTPUT_FILE,
    prompt: str = DEFAULT_PROMPT,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    layouts = _load_slide_layouts(layouts_file)
    schemas = _load_or_create_schemas(layouts, schemas_file)
    client = _create_openrouter_client()
    outline = generate_presentation_outline(
        client=client,
        layouts=layouts,
        prompt=prompt,
        model=model,
    )

    schemas_by_layout_id = {
        schema["layoutId"]: schema for schema in schemas.get("schemas", [])
    }
    outline_by_layout_id = {
        slide["layoutId"]: slide for slide in outline.get("slides", [])
    }
    layouts_by_index: dict[int, dict[str, Any]] = {}
    layout_items = list(enumerate(layouts["layouts"]))

    with ThreadPoolExecutor(max_workers=len(layout_items)) as executor:
        futures = {}
        for index, layout in layout_items:
            layout_id = layout["id"]
            schema = schemas_by_layout_id.get(layout_id)
            if schema is None:
                raise ValueError(f"missing generation schema for layout: {layout_id}")

            futures[
                executor.submit(
                    _generate_materialized_layout,
                    layout=layout,
                    schema=schema,
                    slide_outline=outline_by_layout_id[layout_id],
                    prompt=prompt,
                    model=model,
                )
            ] = index

        for future in as_completed(futures):
            layouts_by_index[futures[future]] = future.result()

    materialized_layouts = [
        layouts_by_index[index] for index in range(len(layout_items))
    ]

    presentation = _validate_slide_layouts({"layouts": materialized_layouts})
    _write_json(output_file, presentation)
    print(f"Saved generated presentation to {output_file}", flush=True)
    return presentation


def _generate_materialized_layout(
    *,
    layout: dict[str, Any],
    schema: dict[str, Any],
    slide_outline: dict[str, Any],
    prompt: str,
    model: str,
) -> dict[str, Any]:
    layout_id = layout["id"]
    print(f"LLM: generating presentation content for {layout_id}.", flush=True)
    content = generate_layout_content(
        client=_create_openrouter_client(),
        schema=schema,
        slide_outline=slide_outline,
        prompt=prompt,
        model=model,
    )
    return apply_content_to_layout(
        layout=layout,
        schema=schema,
        content=content,
    )


def generate_presentation_outline(
    *,
    client: Any,
    layouts: dict[str, Any],
    prompt: str,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    layout_summaries = [
        {
            "slideNumber": index,
            "layoutId": layout["id"],
            "description": layout.get("description"),
            "components": [
                {
                    "id": component["id"],
                    "description": component.get("description"),
                }
                for component in layout.get("components", [])
            ],
        }
        for index, layout in enumerate(layouts["layouts"], start=1)
    ]
    outline_schema = _presentation_outline_schema(layout_summaries)

    print("LLM: generating presentation outline.", flush=True)
    response = client.generate(
        model=model,
        messages=[
            SystemMessage(content=OUTLINE_GENERATION_PROMPT),
            UserMessage(
                content=json.dumps(
                    {
                        "prompt": prompt,
                        "layouts": layout_summaries,
                        "schema": outline_schema,
                    },
                    indent=2,
                )
            ),
        ],
        response_format=JSONSchemaResponse(
            name="presentation_outline",
            strict=False,
            json_schema=outline_schema,
        ),
        extra_body=_openrouter_extra_body(),
    )
    outline = _parse_json_content(response.content)
    _validate_presentation_outline(outline, layout_summaries)
    return outline


def generate_layout_content(
    *,
    client: Any,
    schema: dict[str, Any],
    slide_outline: dict[str, Any],
    prompt: str,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    layout_id = schema["layoutId"]
    json_schema = schema["schema"]
    response = client.generate(
        model=model,
        messages=[
            SystemMessage(content=CONTENT_GENERATION_PROMPT),
            UserMessage(
                content=json.dumps(
                    {
                        "prompt": prompt,
                        "slideOutline": slide_outline,
                        "layoutId": layout_id,
                        "description": schema.get("description"),
                        "schema": json_schema,
                    },
                    indent=2,
                )
            ),
        ],
        response_format=JSONSchemaResponse(
            name=_response_format_name(layout_id),
            strict=False,
            json_schema=json_schema,
        ),
        extra_body=_openrouter_extra_body(),
    )
    content = _parse_json_content(response.content)
    _validate_generated_content_keys(content, json_schema, layout_id)
    return content


def apply_content_to_layout(
    *,
    layout: dict[str, Any],
    schema: dict[str, Any],
    content: dict[str, Any],
) -> dict[str, Any]:
    materialized = deepcopy(layout)

    for field in schema.get("fields", []):
        key = field["key"]
        if key not in content:
            raise ValueError(f"generated content is missing required field: {key}")

        element = _resolve_path(materialized, field["path"])
        _apply_field_value(element, field, content[key])

    return materialized


def _apply_field_value(
    element: dict[str, Any],
    field: dict[str, Any],
    value: Any,
) -> None:
    target = field["target"]

    if target == "text":
        _set_text_value(element, value)
        return

    if target == "image":
        _set_image_value(element, value)
        return

    if target == "items":
        _set_items_value(element, value, field.get("schema", {}))
        return

    if target == "table":
        _set_table_value(element, value)
        return

    if target == "chart":
        _set_chart_value(element, value)
        return

    _apply_element_value_from_schema(element, value, field.get("schema", {}))


def _apply_element_value_from_schema(
    element: dict[str, Any],
    value: Any,
    schema: dict[str, Any],
) -> None:
    element_type = element.get("type")

    if element_type == "text":
        _set_text_value(element, value)
        return

    if element_type == "image":
        _set_image_value(element, value)
        return

    if element_type == "text-list":
        _set_text_list_items(element, value)
        return

    if element_type == "table":
        _set_table_value(element, value)
        return

    if element_type == "chart":
        _set_chart_value(element, value)
        return

    if element_type == "container":
        child = element.get("child")
        if isinstance(child, dict):
            _apply_element_value_from_schema(child, value, schema)
        return

    if element_type in {"flex", "grid", "stack"}:
        _apply_children_value_from_schema(element, value, schema)
        return

    if element_type in {"list-view", "grid-view"}:
        _set_items_value(element, value, schema)


def _apply_children_value_from_schema(
    element: dict[str, Any],
    value: Any,
    schema: dict[str, Any],
) -> None:
    if not isinstance(value, dict):
        return

    properties = schema.get("properties", {})
    for index, child in enumerate(element.get("children") or []):
        key = f"child_{index}_{_target_for_element(child)}"
        if key not in value:
            continue

        child_schema = properties.get(key, {})
        _apply_element_value_from_schema(child, value[key], child_schema)


def _set_text_value(element: dict[str, Any], value: Any) -> None:
    text = _text_from_generated_value(value)
    element.pop("text", None)

    first_run = (element.get("runs") or [{}])[0]
    run: dict[str, Any] = {"text": text}
    if isinstance(first_run, dict) and first_run.get("font") is not None:
        run["font"] = first_run["font"]
    elif element.get("font") is not None:
        run["font"] = element["font"]
    element["runs"] = [run]


def _set_image_value(element: dict[str, Any], value: Any) -> None:
    if not isinstance(value, dict):
        element["name"] = str(value)
        return

    name = value.get("name") or value.get("prompt")
    if name is not None:
        element["name"] = str(name)

    for source_key in ("data", "url", "path"):
        source = value.get(source_key)
        if source:
            element["data"] = str(source)
            return


def _set_items_value(
    element: dict[str, Any],
    value: Any,
    schema: dict[str, Any],
) -> None:
    element_type = element.get("type")

    if element_type == "text-list":
        _set_text_list_items(element, value)
        return

    if element_type in {"list-view", "grid-view"}:
        _materialize_repeated_view(element, value, schema)
        return

    _apply_element_value_from_schema(element, value, schema)


def _set_text_list_items(element: dict[str, Any], value: Any) -> None:
    if not isinstance(value, list):
        raise ValueError("text-list content must be an array")

    items: list[dict[str, Any]] = []
    for item in value:
        items.append({"type": "text", "text": _text_from_generated_value(item)})

    element["items"] = items


def _materialize_repeated_view(
    element: dict[str, Any],
    value: Any,
    schema: dict[str, Any],
) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{element.get('type')} content must be an array")

    item_template = element.get("item")
    if not isinstance(item_template, dict):
        raise ValueError(f"{element.get('type')} is missing an item template")

    item_schema = schema.get("items", {})
    children = []
    for item_value in value:
        child = deepcopy(item_template)
        _apply_element_value_from_schema(child, item_value, item_schema)
        children.append(child)

    original = dict(element)
    if original.get("type") == "list-view":
        replacement = _list_view_to_flex(original, children)
    else:
        replacement = _grid_view_to_grid(original, children)

    element.clear()
    element.update(replacement)


def _list_view_to_flex(
    element: dict[str, Any],
    children: list[dict[str, Any]],
) -> dict[str, Any]:
    replacement = {
        "type": "flex",
        "fixed": element["fixed"],
        "position": element.get("position") or {"x": 0, "y": 0},
        "size": element.get("size") or {"width": 1, "height": 1},
        "direction": element.get("direction") or "column",
        "children": children,
    }
    _copy_optional_keys(
        source=element,
        target=replacement,
        keys=[
            "rotation",
            "wrap",
            "alignItems",
            "justifyContent",
            "gap",
            "columnGap",
            "rowGap",
        ],
    )
    return replacement


def _grid_view_to_grid(
    element: dict[str, Any],
    children: list[dict[str, Any]],
) -> dict[str, Any]:
    replacement = {
        "type": "grid",
        "fixed": element["fixed"],
        "position": element.get("position") or {"x": 0, "y": 0},
        "size": element.get("size") or {"width": 1, "height": 1},
        "columns": element["columns"],
        "children": children,
    }
    _copy_optional_keys(
        source=element,
        target=replacement,
        keys=[
            "rows",
            "rotation",
            "alignItems",
            "justifyItems",
            "gap",
            "columnGap",
            "rowGap",
        ],
    )
    return replacement


def _set_table_value(element: dict[str, Any], value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("table content must be an object")

    if "columns" in value:
        element["columns"] = [
            _table_cell_from_value(item) for item in _as_list(value["columns"])
        ]

    if "rows" in value:
        element["rows"] = [
            [_table_cell_from_value(cell) for cell in _as_list(row)]
            for row in _as_list(value["rows"])
        ]


def _set_chart_value(element: dict[str, Any], value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("chart content must be an object")

    if "title" in value:
        element["title"] = str(value["title"])

    if "data" in value:
        element["data"] = [
            {
                "label": str(item.get("label", "")),
                "value": float(item.get("value", 0)),
            }
            for item in _as_list(value["data"])
            if isinstance(item, dict)
        ]


def _table_cell_from_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        cell = dict(value)
        if "text" not in cell:
            cell["text"] = _text_from_generated_value(value)
        return cell

    return {"text": _text_from_generated_value(value)}


def _resolve_path(root: dict[str, Any], path: str) -> dict[str, Any]:
    current: Any = root

    for part in path.split("."):
        match = PATH_PART_RE.match(part)
        if match is None:
            raise ValueError(f"invalid field path part: {part}")

        key, raw_index = match.groups()
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"field path does not exist: {path}")

        current = current[key]
        if raw_index is not None:
            index = int(raw_index)
            if not isinstance(current, list) or index >= len(current):
                raise ValueError(f"field path index does not exist: {path}")
            current = current[index]

    if not isinstance(current, dict):
        raise ValueError(f"field path must resolve to an object: {path}")

    return current


def _target_for_element(element: dict[str, Any]) -> str:
    element_type = element.get("type")
    if element_type == "text":
        return "text"
    if element_type == "image":
        return "image"
    if element_type in {"text-list", "list-view", "grid-view"}:
        return "items"
    if element_type == "table":
        return "table"
    if element_type == "chart":
        return "chart"
    return "value"


def _text_from_generated_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("text", "title", "name", "prompt", "label"):
            if key in value:
                return str(value[key])
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    if isinstance(value, list):
        return ", ".join(_text_from_generated_value(item) for item in value)

    return str(value)


def _validate_generated_content_keys(
    content: dict[str, Any],
    schema: dict[str, Any],
    layout_id: str,
) -> None:
    required = schema.get("required", [])
    missing = [key for key in required if key not in content]
    if missing:
        raise ValueError(
            f"generated content for {layout_id} is missing required keys: {missing}"
        )


def _presentation_outline_schema(layouts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "slides": {
                "type": "array",
                "minItems": len(layouts),
                "maxItems": len(layouts),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "slideNumber": {"type": "integer"},
                        "layoutId": {"type": "string"},
                        "title": {"type": "string", "minLength": 1},
                        "purpose": {"type": "string", "minLength": 1},
                        "keyPoints": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 8,
                            "items": {"type": "string", "minLength": 1},
                        },
                        "visualDirection": {"type": "string", "minLength": 1},
                        "contentDirection": {"type": "string", "minLength": 1},
                    },
                    "required": [
                        "slideNumber",
                        "layoutId",
                        "title",
                        "purpose",
                        "keyPoints",
                        "visualDirection",
                        "contentDirection",
                    ],
                },
            }
        },
        "required": ["slides"],
    }


def _validate_presentation_outline(
    outline: dict[str, Any],
    layouts: list[dict[str, Any]],
) -> None:
    slides = outline.get("slides")
    if not isinstance(slides, list):
        raise ValueError("presentation outline must include a slides array")

    if len(slides) != len(layouts):
        raise ValueError(
            f"presentation outline must include {len(layouts)} slides, got {len(slides)}"
        )

    for index, (slide, layout) in enumerate(zip(slides, layouts), start=1):
        if not isinstance(slide, dict):
            raise ValueError(f"slide outline {index} must be an object")

        if slide.get("slideNumber") != index:
            raise ValueError(f"slide outline {index} has the wrong slideNumber")

        if slide.get("layoutId") != layout["layoutId"]:
            raise ValueError(
                f"slide outline {index} must use layoutId {layout['layoutId']}"
            )


def _response_format_name(layout_id: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z_]+", "_", f"{layout_id}_content").strip("_")
    if not name:
        return "slide_content"
    if name[0].isdigit():
        return f"slide_{name}"
    return name[:64]


def _load_slide_layouts(layouts_file: Path) -> dict[str, Any]:
    data = _read_json(layouts_file)
    return _validate_slide_layouts(_normalize_null_fixed_flags(data))


def _validate_slide_layouts(data: dict[str, Any]) -> dict[str, Any]:
    return SlideLayouts.model_validate(data).model_dump(mode="json")


def _load_or_create_schemas(
    layouts: dict[str, Any],
    schemas_file: Path,
) -> dict[str, Any]:
    generated_schemas = create_layouts_generation_schemas(layouts)

    if schemas_file.exists():
        schemas = _read_json(schemas_file)
        if schemas == generated_schemas:
            return schemas

        print(f"Regenerating stale schema file {schemas_file}", flush=True)

    _write_json(schemas_file, generated_schemas)
    return generated_schemas


def _copy_optional_keys(
    *,
    source: dict[str, Any],
    target: dict[str, Any],
    keys: list[str],
) -> None:
    for key in keys:
        value = source.get(key)
        if value is not None:
            target[key] = value


def _normalize_null_fixed_flags(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_null_fixed_flags(item) for item in value]

    if isinstance(value, dict):
        normalized = {
            key: _normalize_null_fixed_flags(item) for key, item in value.items()
        }
        if (
            normalized.get("type") in ELEMENT_TYPES
            and normalized.get("fixed") is None
        ):
            normalized["fixed"] = False
        return normalized

    return value


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json(file_path: Path) -> dict[str, Any]:
    with open(file_path, "r") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{file_path} must contain a JSON object")

    return data


def _write_json(file_path: Path, data: dict[str, Any]) -> None:
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a presentation by filling layout schemas with new content."
    )
    parser.add_argument("--layouts", type=Path, default=DEFAULT_LAYOUTS_FILE)
    parser.add_argument("--schemas", type=Path, default=DEFAULT_SCHEMAS_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_presentation(
        layouts_file=args.layouts,
        schemas_file=args.schemas,
        output_file=args.output,
        prompt=args.prompt,
        model=args.model,
    )


if __name__ == "__main__":
    main()
