from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from elements import (
    Chart,
    Container,
    Flex,
    Grid,
    GridView,
    Image,
    List as ListElement,
    ListView,
    RichText,
    Stack,
    Table,
    Text,
)
from llm_models import SlideLayout
from llm_models import SlideLayouts


JsonSchema = dict[str, Any]
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_LAYOUTS_FILE = ASSETS_DIR / "layouts.json"
DEFAULT_SCHEMAS_FILE = ASSETS_DIR / "schemas.json"


def create_layout_generation_schema(layout: SlideLayout | dict[str, Any]) -> dict[str, Any]:
    slide_layout = (
        layout if isinstance(layout, SlideLayout) else SlideLayout.model_validate(layout)
    )
    properties: dict[str, JsonSchema] = {}
    fields: list[dict[str, Any]] = []
    used_keys: set[str] = set()

    for component_index, component in enumerate(slide_layout.components):
        for element_index, element in enumerate(component.elements):
            _collect_element_fields(
                element=element,
                component_id=component.id,
                path=f"components[{component_index}].elements[{element_index}]",
                key_prefix=f"{component.id}_element_{element_index}",
                properties=properties,
                fields=fields,
                used_keys=used_keys,
            )

    return {
        "layoutId": slide_layout.id,
        "description": slide_layout.description,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": list(properties.keys()),
        },
        "fields": fields,
    }


def create_layouts_generation_schemas(
    layouts: SlideLayouts | dict[str, Any],
) -> dict[str, Any]:
    slide_layouts = (
        layouts if isinstance(layouts, SlideLayouts) else SlideLayouts.model_validate(layouts)
    )

    return {
        "schemas": [
            create_layout_generation_schema(layout)
            for layout in slide_layouts.layouts
        ]
    }


def save_layouts_generation_schemas(
    layouts_file: Path = DEFAULT_LAYOUTS_FILE,
    schemas_file: Path = DEFAULT_SCHEMAS_FILE,
) -> dict[str, Any]:
    with open(layouts_file, "r") as f:
        layouts = json.load(f)

    schemas = create_layouts_generation_schemas(layouts)

    schemas_file.parent.mkdir(parents=True, exist_ok=True)
    with open(schemas_file, "w") as f:
        json.dump(schemas, f, indent=2)
        f.write("\n")

    return schemas


def _collect_element_fields(
    *,
    element: Any,
    component_id: str,
    path: str,
    key_prefix: str,
    properties: dict[str, JsonSchema],
    fields: list[dict[str, Any]],
    used_keys: set[str],
) -> None:
    if _is_fixed(element):
        return

    if isinstance(element, (Text, RichText, Image, ListElement, Table, Chart)):
        _add_field(
            key_prefix=key_prefix,
            target=_target_for_element(element),
            schema=_schema_for_element_value(element),
            component_id=component_id,
            path=path,
            element_type=element.type,
            properties=properties,
            fields=fields,
            used_keys=used_keys,
        )
        return

    if isinstance(element, Container):
        if element.child is not None:
            _collect_element_fields(
                element=element.child,
                component_id=component_id,
                path=f"{path}.child",
                key_prefix=f"{key_prefix}_child",
                properties=properties,
                fields=fields,
                used_keys=used_keys,
            )
        return

    if isinstance(element, (Flex, Grid, Stack)):
        for index, child in enumerate(element.children):
            _collect_element_fields(
                element=child,
                component_id=component_id,
                path=f"{path}.children[{index}]",
                key_prefix=f"{key_prefix}_child_{index}",
                properties=properties,
                fields=fields,
                used_keys=used_keys,
            )
        return

    if isinstance(element, (ListView, GridView)):
        item_schema = _schema_for_repeated_item(element.item)

        if item_schema is None:
            return

        schema: JsonSchema = {
            "type": "array",
            "items": item_schema,
        }
        _set_optional_schema_number(schema, "minItems", element.minCount)
        _set_optional_schema_number(schema, "maxItems", element.maxCount)

        if "minItems" not in schema:
            schema["minItems"] = element.count
        if "maxItems" not in schema:
            schema["maxItems"] = element.count

        _add_field(
            key_prefix=key_prefix,
            target="items",
            schema=schema,
            component_id=component_id,
            path=path,
            element_type=element.type,
            properties=properties,
            fields=fields,
            used_keys=used_keys,
        )


def _add_field(
    *,
    key_prefix: str,
    target: str,
    schema: JsonSchema,
    component_id: str,
    path: str,
    element_type: str,
    properties: dict[str, JsonSchema],
    fields: list[dict[str, Any]],
    used_keys: set[str],
) -> None:
    key = _unique_key(f"{key_prefix}_{target}", used_keys)
    properties[key] = schema
    fields.append(
        {
            "key": key,
            "componentId": component_id,
            "path": path,
            "elementType": element_type,
            "target": target,
            "schema": schema,
        }
    )


def _schema_for_repeated_item(element: Any) -> JsonSchema | None:
    if _is_fixed(element):
        return None

    if isinstance(element, (Text, RichText, Image, ListElement, Table, Chart)):
        return _schema_for_element_value(element)

    if isinstance(element, Container):
        return _schema_for_repeated_item(element.child) if element.child else None

    if isinstance(element, (Flex, Grid, Stack)):
        properties: dict[str, JsonSchema] = {}
        required: list[str] = []

        for index, child in enumerate(element.children):
            child_schema = _schema_for_repeated_item(child)

            if child_schema is None:
                continue

            key = f"child_{index}_{_target_for_element(child)}"
            properties[key] = child_schema
            required.append(key)

        if not properties:
            return None

        return {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": required,
        }

    if isinstance(element, (ListView, GridView)):
        item_schema = _schema_for_repeated_item(element.item)

        if item_schema is None:
            return None

        schema: JsonSchema = {"type": "array", "items": item_schema}
        _set_optional_schema_number(schema, "minItems", element.minCount)
        _set_optional_schema_number(schema, "maxItems", element.maxCount)
        return schema

    return None


def _schema_for_element_value(element: Any) -> JsonSchema:
    if isinstance(element, Text):
        return _string_schema(element.minLength, element.maxLength)

    if isinstance(element, RichText):
        return _string_schema(element.minLength, element.maxLength)

    if isinstance(element, Image):
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Prompt or description for the replacement image.",
                    "minLength": 1,
                },
                "name": {"type": "string"},
            },
            "required": ["prompt"],
        }

    if isinstance(element, ListElement):
        schema: JsonSchema = {
            "type": "array",
            "items": _string_schema(element.minItemLength, element.maxItemLength),
        }
        _set_optional_schema_number(schema, "minItems", element.minItems)
        _set_optional_schema_number(schema, "maxItems", element.maxItems)
        return schema

    if isinstance(element, Table):
        cell_schema = _table_cell_string_schema(element)
        row_schema: JsonSchema = {"type": "array", "items": cell_schema}
        _set_optional_schema_number(row_schema, "minItems", element.minColumns)
        _set_optional_schema_number(row_schema, "maxItems", element.maxColumns)

        rows_schema: JsonSchema = {"type": "array", "items": row_schema}
        _set_optional_schema_number(rows_schema, "minItems", element.minRows)
        _set_optional_schema_number(rows_schema, "maxItems", element.maxRows)

        columns_schema: JsonSchema = {"type": "array", "items": cell_schema}
        _set_optional_schema_number(columns_schema, "minItems", element.minColumns)
        _set_optional_schema_number(columns_schema, "maxItems", element.maxColumns)

        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "columns": columns_schema,
                "rows": rows_schema,
            },
            "required": ["columns", "rows"],
        }

    if isinstance(element, Chart):
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string"},
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label": {"type": "string"},
                            "value": {"type": "number"},
                        },
                        "required": ["label", "value"],
                    },
                },
            },
            "required": ["data"],
        }

    return {"type": "object"}


def _table_cell_string_schema(element: Table) -> JsonSchema:
    cells = [*element.columns, *(cell for row in element.rows for cell in row)]
    min_length = _max_optional_int(cell.minLength for cell in cells)
    max_length = _min_optional_int(cell.maxLength for cell in cells)
    return _string_schema(min_length, max_length)


def _target_for_element(element: Any) -> str:
    if isinstance(element, (Text, RichText)):
        return "text"
    if isinstance(element, Image):
        return "image"
    if isinstance(element, ListElement):
        return "items"
    if isinstance(element, Table):
        return "table"
    if isinstance(element, Chart):
        return "chart"
    return "value"


def _string_schema(min_length: int | None, max_length: int | None) -> JsonSchema:
    schema: JsonSchema = {"type": "string"}
    _set_optional_schema_number(schema, "minLength", min_length)
    _set_optional_schema_number(schema, "maxLength", max_length)
    return schema


def _set_optional_schema_number(
    schema: JsonSchema,
    key: str,
    value: int | None,
) -> None:
    if value is not None:
        schema[key] = value


def _max_optional_int(values: Any) -> int | None:
    numbers = [value for value in values if value is not None]
    return max(numbers) if numbers else None


def _min_optional_int(values: Any) -> int | None:
    numbers = [value for value in values if value is not None]
    return min(numbers) if numbers else None


def _is_fixed(element: Any) -> bool:
    return getattr(element, "fixed", False) is True


def _unique_key(value: str, used_keys: set[str]) -> str:
    base = _schema_key(value)
    key = base
    index = 2

    while key in used_keys:
        key = f"{base}_{index}"
        index += 1

    used_keys.add(key)
    return key


def _schema_key(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", value)).strip("_")


def main() -> None:
    schemas = save_layouts_generation_schemas()
    print(
        f"Saved {len(schemas['schemas'])} generation schema(s) to {DEFAULT_SCHEMAS_FILE}"
    )


if __name__ == "__main__":
    main()
