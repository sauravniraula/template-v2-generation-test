"""Create reusable slide components from exported presentation JSON."""

from __future__ import annotations

import json
import os
from typing import Any

from llmai import OpenAIApiType, OpenAIClientConfig, get_client
from llmai.client import BaseClient, ClientConfig
from llmai.shared import JSONSchemaResponse, SystemMessage, UserMessage

from llm_models import SlideComponents

DEFAULT_MODEL = "gpt-5.4"

SYSTEM_PROMPT = """You convert exported presentation JSON into reusable slide components.

Slide components are reusable groups of slide elements that can be combined to recreate every
slide in the deck. Identify repeated layout, typography, visual treatments, and semantic blocks.

Rules:
- Return only JSON that matches the SlideComponents schema.
- The top-level object must have a "components" array.
- Each component must have an "id", "descritpion", and "elements"; it may also include
  "position" and "size" for the component's local bounds.
- The field name is intentionally "descritpion"; do not rename it to "description".
- Use concise lower_snake_case ids between 3 and 50 characters.
- Keep "descritpion" between 50 and 200 characters and describe where the component is reused.
- Elements must use the supported discriminated element types: text, rich-text, container, image,
  list, table, rectangle, ellipse, line, chart, flex, grid, and stack.
- Treat every component as its own local coordinate system. The component's top-left is (0, 0);
  element positions must be relative to that local origin, not copied from the slide position.
- If component-level position is present in this reusable component library, set it to the slide
  position where this component is most commonly placed across the presentation.
- If component-level size is present, set it to the component's local bounding-box size.
- When a component is extracted from slide coordinates, subtract the component's bounding-box
  top-left from all child positions so the reusable component starts at (0, 0).
- Keep every child element position local to the component, even when component.position stores
  the common slide placement.
- Use stack elements to group multiple absolutely positioned children in component-local
  coordinates; child order inside a stack is the visual stacking order.
- Prefer reusable templates over one-off slide copies: headers, footers, date chips, title blocks,
  stat cards, image placeholders, comparison rows, timelines, icon labels, section markers, and
  repeated background or divider treatments.
- Preserve useful coordinates, sizes, colors, fonts, alignment, fills, strokes, and placeholder
  text constraints when they are visible in the source JSON.
- Do not include raw PowerPoint shape objects. Convert them to SlideElement objects.
"""


def create_slide_components(
    presentation: dict[str, Any],
    *,
    client: BaseClient | None = None,
    config: ClientConfig | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float | None = 0.1,
    max_tokens: int | None = None,
) -> SlideComponents:
    """Create reusable slide components from presentation.json content.

    Args:
        presentation: Parsed presentation.json content.
        client: Optional preconfigured llmai client. Useful for tests or custom providers.
        config: Optional llmai client config used with get_client.
        model: LLM model name. Defaults to SLIDE_COMPONENTS_MODEL, LLM_MODEL, or DEFAULT_MODEL.
        api_key: Optional OpenAI-compatible API key for the default client.
        base_url: Optional OpenAI-compatible base URL for the default client.
        temperature: LLM sampling temperature.
        max_tokens: Optional response token limit.

    Returns:
        A validated SlideComponents instance.
    """

    if not isinstance(presentation, dict):
        raise TypeError(
            "presentation must be a dict containing presentation.json content"
        )

    llm_client = _resolve_client(
        client=client,
        config=config,
        api_key=api_key,
        base_url=base_url,
    )
    resolved_model = model or _first_env("SLIDE_COMPONENTS_MODEL", "LLM_MODEL")
    if not resolved_model:
        resolved_model = DEFAULT_MODEL

    slide_count = len(presentation.get("slides", []))
    print(
        f"LLM: creating reusable slide components from {slide_count} slides with model {resolved_model}...",
        flush=True,
    )
    response = llm_client.generate(
        model=resolved_model,
        messages=[
            SystemMessage(content=SYSTEM_PROMPT),
            UserMessage(content=_presentation_prompt(presentation)),
        ],
        temperature=temperature,
        response_format=JSONSchemaResponse(
            name="slide_components",
            strict=False,
            json_schema=SlideComponents,
        ),
        max_tokens=max_tokens,
    )

    print("LLM: received slide components response; validating schema...", flush=True)
    components = _parse_slide_components(response.content)
    print(
        f"LLM: validated {len(components.components)} reusable slide components.",
        flush=True,
    )
    return components


def _resolve_client(
    *,
    client: BaseClient | None,
    config: ClientConfig | None,
    api_key: str | None,
    base_url: str | None,
) -> BaseClient:
    if client is not None:
        if config is not None or api_key is not None or base_url is not None:
            raise ValueError(
                "Pass either client, config, or api_key/base_url; not multiple."
            )
        return client

    if config is not None:
        if api_key is not None or base_url is not None:
            raise ValueError("Pass either config or api_key/base_url; not both.")
        return get_client(config=config)

    resolved_api_key = api_key or _first_env("OPENAI_API_KEY", "LLM_API_KEY")
    if not resolved_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY or LLM_API_KEY is required when no llmai client/config is provided"
        )

    return get_client(
        config=OpenAIClientConfig(
            api_type=OpenAIApiType.RESPONSES,
            api_key=resolved_api_key,
            base_url=base_url or _first_env("OPENAI_BASE_URL", "LLM_BASE_URL"),
        )
    )


def _presentation_prompt(presentation: dict[str, Any]) -> str:
    presentation_json = json.dumps(
        presentation,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "Create a reusable SlideComponents library from this presentation.json content.\n\n"
        f"{presentation_json}"
    )


def _parse_slide_components(content: Any) -> SlideComponents:
    if isinstance(content, SlideComponents):
        return content

    if isinstance(content, str):
        return SlideComponents.model_validate_json(content)

    return SlideComponents.model_validate(content)


def _first_env(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


__all__ = [
    "create_slide_components",
]
