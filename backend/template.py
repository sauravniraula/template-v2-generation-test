import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from json import JSONDecodeError
from typing import Any

from llmai import (
    OpenAIClient,
    OpenRouterClient,
    OpenRouterClientConfig,
    ReasoningEffort,
    ReasoningEffortValue,
)
from llmai.shared.messages import AssistantMessage, SystemMessage, UserMessage
from llmai.shared.response_formats import TextResponse
from pydantic import BaseModel, ValidationError

from layout_normalizer import normalize_slide_layouts
from llm_models import SlideLayout, SlideLayouts
from settings import SETTINGS

DEFAULT_MODEL = "z-ai/glm-4.7"
DEFAULT_REASONING_EFFORT = ReasoningEffort(effort=ReasoningEffortValue.HIGH)
DEFAULT_VALIDATION_RETRIES = 3
OPENROUTER_PROVIDER_ORDER = ("cerebras/fp16", "google-vertex")

GENERATE_SLIDE_LAYOUTS_PROMPT = """
Create slide layout from the provided shape objects.
The user prompt contains one slide number and all shape objects from that slide.

# Steps
1. Review all shapes in the slide.
2. Group related shapes into slide components.
3. Convert each group into SlideComponent objects.
4. Return exactly one SlideLayout.

# Slide Layout Rules
- Use a 1280x720 slide coordinate system.
- Layout `id` must be a concise lower_snake_case name.
- The layout must include all the visible components present in the slide.
- Preserve the visual stacking order of the original slide.

# Slide Component Rules
- `SlideComponent.position` and `SlideComponent.size` must be in slide coordinates.
- `SlideComponent.position` must be the top-left of the tight bounding box occupied by that component in slide space.
- `SlideComponent.size` must be the tight total space occupied by the component's elements.
- Every element inside a component must use positions relative to the component's top-left, so the minimum element x/y in each component should normally be 0/0.
- Set `fixed: true` for static layout/decorative content that should stay unchanged when a new slide is generated from this layout.
- Set `fixed: false` for replaceable content placeholders. These non-fixed fields will be included in the later LLM generation schema and replaced when generating a new slide.
- Component `id` values must be concise lower_snake_case names.
- Group only related shapes into the same component. Eg: `contact_info`, `product_list`, `timeline`, `title_description`, etc.
- For related lists, cards, timelines, menus, grids, or repeated items, create one component for the full group.
- Use `container`, `flex`, `grid`, and `stack` when they make positioning, resizing, or grouping clearer.
- For repeated same-structure items, use `list-view` or `grid-view` with one representative `item` element and `count` rather than duplicating the same element many times.
- Use `list-view` for repeated same-structure items in one row or column.
- Use `grid-view` for repeated same-structure items arranged across multiple rows and columns.
- Use `flex` or `grid` only when children are different elements or need distinct per-child content/positioning.
- Use `text` for text boxes. Store content in optional `runs` as `TextRun` objects; do not output a top-level `text` field on text elements.
- Use `text-list` for text-only lists. Each item must be a text item with `type: "text"` and `text`.
- Preserve source content exactly: text strings, text runs, text-list item text, table cell text, image names, image URLs/paths, and image data must match the input shapes without rewriting, summarizing, translating, or inventing replacements.
- Provide schema fields wherever the element supports them:
  - text/table cells: `minLength` and `maxLength`
  - text-list: `minItems`, `maxItems`, `minItemLength`, and `maxItemLength`
  - table: `minColumns`, `maxColumns`, `minRows`, and `maxRows`
  - flex/grid/stack: `minChildren` and `maxChildren`
  - list-view/grid-view: `minCount` and `maxCount`

# Output Rules
- Return raw JSON only matching the SlideLayout schema.
- Do not include markdown fences, comments, explanations, or any text before or after the JSON object.
"""


def generate_slide_layouts(
    presentation: dict,
    validation_retries: int = DEFAULT_VALIDATION_RETRIES,
    retry_loop: bool = True,
    response_file: str | None = None,
):
    slides = presentation.get("slides", [])
    slide_count = len(slides)
    print(
        f"LLM: preparing to generate slide layouts from {slide_count} slides.",
        flush=True,
    )

    layouts_by_slide: dict[int, dict[str, Any]] = {}
    if slide_count:
        with ThreadPoolExecutor(max_workers=slide_count) as executor:
            futures = {
                executor.submit(
                    _generate_slide_layout_for_slide,
                    slide_index=slide_index,
                    slide=slide,
                    slide_count=slide_count,
                    validation_retries=validation_retries,
                    retry_loop=retry_loop,
                ): slide_index
                for slide_index, slide in enumerate(slides, start=1)
            }
            for future in as_completed(futures):
                slide_index = futures[future]
                layouts_by_slide[slide_index] = future.result()

    layouts = [
        layouts_by_slide[slide_index] for slide_index in range(1, slide_count + 1)
    ]

    result = normalize_slide_layouts(
        _validate_output_model(
            {"layouts": layouts},
            SlideLayouts,
        )
    )
    _save_json_response(response_file, result)
    return result


def _generate_slide_layout_for_slide(
    *,
    slide_index: int,
    slide: dict[str, Any],
    slide_count: int,
    validation_retries: int,
    retry_loop: bool,
) -> dict[str, Any]:
    print(
        f"LLM: generating slide layout for slide {slide_index}/{slide_count}.",
        flush=True,
    )
    payload = {
        "slide": slide_index,
        "shapes": slide.get("shapes", []),
    }
    response = _generate_with_validation_retries(
        client=_create_openrouter_client(),
        model=DEFAULT_MODEL,
        messages=[
            SystemMessage(content=GENERATE_SLIDE_LAYOUTS_PROMPT),
            UserMessage(content=json.dumps(payload, indent=2)),
        ],
        label=f"slide {slide_index} layout",
        output_model=SlideLayout,
        validation_retries=validation_retries,
        retry_loop=retry_loop,
        response_file=None,
        extra_body=_openrouter_extra_body(),
    )
    return response


def _generate_with_validation_retries(
    *,
    client: OpenAIClient,
    model: str,
    messages: list[Any],
    label: str,
    output_model: type[BaseModel],
    validation_retries: int,
    retry_loop: bool,
    response_file: str | None,
    extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not retry_loop:
        return _generate_one_shot(
            client=client,
            model=model,
            messages=messages,
            label=label,
            output_model=output_model,
            response_file=response_file,
            extra_body=extra_body,
        )

    last_error: Exception | None = None
    attempt = 0

    while True:
        attempt += 1
        print(
            f"LLM: generating {label} repair-loop attempt {attempt} with {model}.",
            flush=True,
        )
        try:
            response = client.generate(
                model=model,
                messages=messages,
                response_format=TextResponse(),
                extra_body=extra_body,
            )
        except Exception as exc:
            last_error = exc
            print(
                f"LLM: {label} generation failed before parsing: {exc}",
                flush=True,
            )

            if not _should_retry_generation_error(exc, attempt, validation_retries):
                print(
                    f"LLM: exhausted generation retries for {label}.",
                    flush=True,
                )
                raise

            print(f"LLM: asking model to retry {label} after error.", flush=True)
            messages = _messages_for_generation_error_retry(
                messages=messages,
                label=label,
                error=exc,
            )
            continue

        try:
            print(f"LLM: received {label}; parsing JSON.", flush=True)
            parsed = _parse_json_content(response.content)
            print(f"LLM: validating {label} with {output_model.__name__}.", flush=True)
            result = _validate_output_model(parsed, output_model)
            _save_json_response(response_file, result)
            print(f"LLM: parsed and validated {label}.", flush=True)
            return result
        except ValidationError as exc:
            last_error = exc
            print(
                f"LLM: {label} failed {output_model.__name__} validation with {exc.error_count()} errors.",
                flush=True,
            )

            print(f"LLM: asking model to fix {label} validation errors.", flush=True)
            messages = _messages_for_model_validation_retry(
                messages=messages,
                response=response,
                label=label,
                output_model=output_model,
                error=exc,
                invalid_response=parsed,
            )
        except (JSONDecodeError, ValueError) as exc:
            last_error = exc
            print(f"LLM: {label} JSON parsing failed.", flush=True)

            print(f"LLM: asking model to repair {label}.", flush=True)
            messages = _messages_for_json_repair_retry(
                messages=messages,
                response=response,
                label=label,
                error=exc,
            )

    if last_error is not None:
        raise last_error

    raise RuntimeError(f"LLM failed to generate {label}")


def _should_retry_generation_error(
    error: Exception,
    attempt: int,
    validation_retries: int,
) -> bool:
    del error
    return attempt <= validation_retries


def _generate_one_shot(
    *,
    client: OpenAIClient,
    model: str,
    messages: list[Any],
    label: str,
    output_model: type[BaseModel],
    response_file: str | None,
    extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    print(f"LLM: generating {label} once with {model}.", flush=True)
    response = client.generate(
        model=model,
        messages=messages,
        response_format=TextResponse(),
        extra_body=extra_body,
    )
    print(f"LLM: parsing one-shot {label} JSON.", flush=True)
    parsed = _parse_json_content(response.content)
    print(f"LLM: validating one-shot {label} with {output_model.__name__}.", flush=True)
    result = _validate_output_model(parsed, output_model)
    _save_json_response(response_file, result)
    return result


def _validate_output_model(
    parsed: dict[str, Any],
    output_model: type[BaseModel],
) -> dict[str, Any]:
    validated = output_model.model_validate(parsed)
    return validated.model_dump(mode="json")


def _save_json_response(file_path: str | None, content: dict[str, Any]) -> None:
    if not file_path:
        return

    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(content, f, indent=2)
        f.write("\n")

    print(f"LLM: saved validated response to {file_path}.", flush=True)


def _save_raw_response(file_path: str | None, content: Any) -> None:
    if not file_path:
        return

    text_content = _text_from_content(content)
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(file_path, "w") as f:
        if text_content is not None:
            f.write(text_content)
        else:
            json.dump(content, f, indent=2, default=str)
        f.write("\n")

    print(f"LLM: saved raw response to {file_path}.", flush=True)


def _create_openrouter_client() -> OpenAIClient:
    if SETTINGS.openrouter_api_key is None:
        raise ValueError("OPENROUTER_API_KEY is required for slide generation")

    return OpenRouterClient(
        config=OpenRouterClientConfig(
            api_key=SETTINGS.openrouter_api_key,
            base_url=SETTINGS.openrouter_base_url,
        )
    )


def _openrouter_extra_body() -> dict[str, Any]:
    provider_order = list(OPENROUTER_PROVIDER_ORDER)
    return {
        "provider": {
            "order": provider_order,
            "only": list(provider_order),
            "allow_fallbacks": False,
        },
        "reasoning": {
            "effort": DEFAULT_REASONING_EFFORT.effort.value,
            "exclude": True,
        },
    }


def _parse_json_content(content: Any) -> dict[str, Any]:
    text_content = _text_from_content(content)

    if text_content is not None:
        parsed = json.loads(text_content)
    else:
        parsed = content

    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")

    return parsed


def _text_from_content(content: Any) -> str | None:
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
            continue

        text = getattr(part, "text", None)
        if isinstance(text, str):
            parts.append(text)

    return "".join(parts) if parts else None


def _messages_for_generation_error_retry(
    *,
    messages: list[Any],
    label: str,
    error: Exception,
) -> list[Any]:
    return [
        *messages,
        UserMessage(
            content=_json_repair_prompt(
                label=label,
                invalid_response=None,
                error=error,
            )
        ),
    ]


def _messages_for_json_repair_retry(
    *,
    messages: list[Any],
    response: Any,
    label: str,
    error: Exception,
) -> list[Any]:
    invalid_response = _text_from_content(response.content) or response.content
    response_messages = getattr(response, "messages", None)
    if response_messages:
        retry_messages = list(response_messages)
    else:
        retry_messages = [
            *messages,
            AssistantMessage(content=[_json_dumps_for_prompt(invalid_response)]),
        ]

    retry_messages.append(
        UserMessage(
            content=_json_repair_prompt(
                label=label,
                invalid_response=invalid_response,
                error=error,
            )
        )
    )
    return retry_messages


def _messages_for_model_validation_retry(
    *,
    messages: list[Any],
    response: Any,
    label: str,
    output_model: type[BaseModel],
    error: ValidationError,
    invalid_response: dict[str, Any],
) -> list[Any]:
    response_messages = getattr(response, "messages", None)
    if response_messages:
        retry_messages = list(response_messages)
    else:
        retry_messages = [
            *messages,
            AssistantMessage(content=[_json_dumps_for_prompt(invalid_response)]),
        ]

    retry_messages.append(
        UserMessage(
            content=_model_validation_repair_prompt(
                label=label,
                output_model=output_model,
                invalid_response=invalid_response,
                error=error,
            )
        )
    )
    return retry_messages


def _json_repair_prompt(
    *,
    label: str,
    invalid_response: Any | None,
    error: Exception,
) -> str:
    parts = [
        f"The previous {label} response was not a valid JSON object for this task.",
        "Return a complete replacement JSON object.",
        "Return raw JSON only. Do not include markdown fences, comments, explanations, or any text before or after the JSON object.",
        "",
        "parse_errors:",
        _format_error_for_prompt(error),
    ]

    if invalid_response is not None:
        parts.extend(
            [
                "",
                "invalid_response:",
                _json_dumps_for_prompt(invalid_response),
            ]
        )

    return "\n".join(parts)


def _model_validation_repair_prompt(
    *,
    label: str,
    output_model: type[BaseModel],
    invalid_response: dict[str, Any],
    error: ValidationError,
) -> str:
    return "\n".join(
        [
            f"The previous {label} response was valid JSON but did not match the required {output_model.__name__} schema.",
            "Return a complete replacement JSON object that validates against the model.",
            "Return raw JSON only. Do not include markdown fences, comments, explanations, or any text before or after the JSON object.",
            "",
            "validation_errors:",
            _format_validation_error_for_prompt(error),
            "",
            "required_json_schema:",
            _json_dumps_for_prompt(output_model.model_json_schema()),
            "",
            "invalid_response:",
            _json_dumps_for_prompt(invalid_response),
        ]
    )


def _format_error_for_prompt(error: Exception) -> str:
    return _json_dumps_for_prompt([{"type": type(error).__name__, "msg": str(error)}])


def _format_validation_error_for_prompt(error: ValidationError) -> str:
    return _json_dumps_for_prompt(error.errors())


def _json_dumps_for_prompt(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return str(value)
