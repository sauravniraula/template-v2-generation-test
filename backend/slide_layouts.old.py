"""Create per-slide layouts from exported presentation JSON and components."""

from __future__ import annotations

import json
from typing import Any

from llmai.client import BaseClient, ClientConfig
from llmai.shared import (
    AssistantMessage,
    JSONSchemaResponse,
    SystemMessage,
    UserMessage,
)
from pydantic import ValidationError

from llm_models import SlideComponents, SlideLayouts
from  import DEFAULT_MODEL, _first_env, _resolve_client

DEFAULT_VALIDATION_RETRIES = 2


SYSTEM_PROMPT = """You convert exported presentation JSON into one reusable-component layout per slide.

A slide layout describes which SlideComponent instances appear on a slide and where each component
is placed in slide coordinates. SlideComponent.position and SlideComponent.size are the component's
slide-space bounds in a layout. Each component's inner elements remain in component-local
coordinates where the component top-left is (0, 0).

Rules:
- Return only JSON that matches the SlideLayouts schema.
- The top-level object must have a "layouts" array.
- Return exactly one layout per slide, in the same order as presentation.slides.
- Use ids like "slide_01_layout", "slide_02_layout", etc.
- Each layout must have "id", "description", and "components".
- Each layout component must include "id", "descritpion", "position", "size", and "elements".
- The field name is intentionally "descritpion"; do not rename it to "description" on components.
- For each layout component, set position to the component's top-left placement on the slide.
- For each layout component, set size to the rendered component bounds on the slide.
- Do not convert child element positions back into slide coordinates. Child positions must stay
  relative to the component's top-left local origin.
- Reuse the provided component library wherever possible. Preserve component ids and local element
  structure when placing reusable components into slide layouts.
- If a slide has a necessary unique block that is not covered by the component library, create an
  inline SlideComponent for that block with local elements and slide-space position/size.
"""


def create_slide_layouts(
    presentation: dict[str, Any],
    slide_components: SlideComponents | dict[str, Any] | str | None = None,
    *,
    client: BaseClient | None = None,
    config: ClientConfig | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float | None = 0.1,
    max_tokens: int | None = None,
    validation_retries: int = DEFAULT_VALIDATION_RETRIES,
) -> SlideLayouts:
    """Create one slide layout for every slide in presentation.json content."""

    if not isinstance(presentation, dict):
        raise TypeError("presentation must be a dict containing presentation.json content")

    slides = _get_slides(presentation)
    components = _parse_slide_components(slide_components)
    llm_client = _resolve_client(
        client=client,
        config=config,
        api_key=api_key,
        base_url=base_url,
    )

    resolved_model = model or _first_env("SLIDE_LAYOUTS_MODEL", "LLM_MODEL")
    if not resolved_model:
        resolved_model = DEFAULT_MODEL

    component_count = len(components.components) if components is not None else 0
    print(
        f"LLM: creating layouts for {len(slides)} slides with {component_count} reusable components using model {resolved_model}...",
        flush=True,
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        UserMessage(
            content=_layout_prompt(
                presentation=presentation,
                slide_count=len(slides),
                slide_components=components,
            )
        ),
    ]
    last_error: ValidationError | ValueError | None = None

    for attempt in range(validation_retries + 1):
        print(
            f"LLM: generating slide layouts attempt {attempt + 1}/{validation_retries + 1}...",
            flush=True,
        )
        response = llm_client.generate(
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            response_format=JSONSchemaResponse(
                name="slide_layouts",
                strict=False,
                json_schema=SlideLayouts,
            ),
            max_tokens=max_tokens,
        )

        try:
            print("LLM: received slide layouts response; validating schema...", flush=True)
            layouts = _parse_slide_layouts(response.content)
            _validate_layout_count(layouts, expected_count=len(slides))
            print(
                f"LLM: validated {len(layouts.layouts)} slide layouts.",
                flush=True,
            )
            return layouts
        except (ValidationError, ValueError) as exc:
            last_error = exc
            if attempt >= validation_retries:
                print(
                    "LLM: slide layouts response still failed validation after all retries.",
                    flush=True,
                )
                raise

            print(
                "LLM: slide layouts validation failed; sending errors back for repair...",
                flush=True,
            )
            response_messages = getattr(response, "messages", None)
            if response_messages:
                messages = list(response_messages)
            else:
                messages.append(
                    AssistantMessage(content=[_json_dumps_for_prompt(response.content)])
                )

            messages.append(
                UserMessage(
                    content=_validation_repair_prompt(
                        invalid_response=response.content,
                        error=exc,
                        expected_slide_count=len(slides),
                    )
                )
            )

    if last_error is not None:
        raise last_error

    raise RuntimeError("Slide layout generation failed without a validation error")


def _get_slides(presentation: dict[str, Any]) -> list[Any]:
    slides = presentation.get("slides")
    if not isinstance(slides, list):
        raise ValueError("presentation must contain a slides list")
    if not slides:
        raise ValueError("presentation must contain at least one slide")
    return slides


def _layout_prompt(
    *,
    presentation: dict[str, Any],
    slide_count: int,
    slide_components: SlideComponents | None,
) -> str:
    presentation_json = json.dumps(
        presentation,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    parts = [
        f"Create exactly {slide_count} SlideLayouts from this presentation.json content.",
        "",
        "presentation_json:",
        presentation_json,
    ]

    if slide_components is not None:
        parts.extend(
            [
                "",
                "slide_components_json:",
                slide_components.model_dump_json(),
            ]
        )

    return "\n".join(parts)


def _parse_slide_components(
    slide_components: SlideComponents | dict[str, Any] | str | None,
) -> SlideComponents | None:
    if slide_components is None:
        return None

    if isinstance(slide_components, SlideComponents):
        return slide_components

    if isinstance(slide_components, str):
        return SlideComponents.model_validate_json(slide_components)

    return SlideComponents.model_validate(slide_components)


def _parse_slide_layouts(content: Any) -> SlideLayouts:
    if isinstance(content, SlideLayouts):
        return content

    if isinstance(content, str):
        return SlideLayouts.model_validate_json(content)

    return SlideLayouts.model_validate(content)


def _validate_layout_count(layouts: SlideLayouts, *, expected_count: int) -> None:
    if len(layouts.layouts) != expected_count:
        raise ValueError(
            f"Expected {expected_count} slide layouts, got {len(layouts.layouts)}"
        )


def _validation_repair_prompt(
    *,
    invalid_response: Any,
    error: ValidationError | ValueError,
    expected_slide_count: int,
) -> str:
    return "\n".join(
        [
            "The previous SlideLayouts response failed validation.",
            "Fix it and return a complete replacement JSON object that matches the SlideLayouts schema.",
            f"Return exactly {expected_slide_count} layouts.",
            "",
            "validation_errors:",
            _format_validation_error(error),
            "",
            "invalid_response:",
            _json_dumps_for_prompt(invalid_response),
        ]
    )


def _format_validation_error(error: ValidationError | ValueError) -> str:
    if isinstance(error, ValidationError):
        return _json_dumps_for_prompt(error.errors())

    return _json_dumps_for_prompt([{"msg": str(error), "type": "value_error"}])


def _json_dumps_for_prompt(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return str(value)


__all__ = [
    "create_slide_layouts",
]
