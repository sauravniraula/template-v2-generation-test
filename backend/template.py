import json
import os
from json import JSONDecodeError
from typing import Any

from llmai import (
    OpenAIApiType,
    OpenAIClient,
    OpenAIClientConfig,
    ReasoningEffort,
    ReasoningEffortValue,
)
from llmai.shared.messages import AssistantMessage, SystemMessage, UserMessage
from llmai.shared.response_formats import TextResponse
from pydantic import BaseModel, ValidationError

from llm_models import SlideComponents, SlideLayouts
from settings import SETTINGS

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_REASONING_EFFORT = ReasoningEffort(effort=ReasoningEffortValue.HIGH)
DEFAULT_VALIDATION_RETRIES = 3

GENERATE_SLIDE_COMPONENTS_PROMPT = """
Create reusable slide components from the the given slides with the shapes.

# Steps
1. Go through shapes present in all the slides.
2. Identify how each shapes are used in the slide.
3. Organize the shapes present in each slide into logical groups like `promption_card`, `title_description', 'contact_info', etc.
4. Now find the similar structured groups across slides to create slide components.
5. For each group of shapes create a slide component.
6. Check if enough slide components are created to cover all the slides and those components can be reused to create those slides.

# Slide Component Rules
- Position of each element in a component should be relative to the component position.
- Position and Size of each component should be average position and size across all the slides.
- If there is list of items/cards, the component should be the full list not just a single item because they are related and should be treated as a single unit.
- Component should contain all items present in the slides. For example, for list of items, it should contain all the items present in the slides, not just a single item.
- Don't create components with elements that are not related to each other.
- Make sure the generated component library is complete enough to recreate every original slide.
- Do not stop until every visible slide element belongs to at least one reusable or slide-specific component.
- If a visible slide element cannot fit an existing reusable component, create an additional component for that element or group so the original slide can still be reconstructed from components.

# Output Rules
- Return raw JSON only. Do not include markdown fences, comments, explanations, or any text before or after the JSON object.
"""


def generate_slide_components(
    presentation: dict,
    validation_retries: int = DEFAULT_VALIDATION_RETRIES,
    retry_loop: bool = True,
    response_file: str | None = None,
):

    client = _create_google_client()

    slide_count = len(presentation.get("slides", []))
    print(
        f"LLM: preparing to generate slide components from {slide_count} slides.",
        flush=True,
    )
    user_message = f"- Presentation:\n{presentation}"
    messages = [
        SystemMessage(content=GENERATE_SLIDE_COMPONENTS_PROMPT),
        UserMessage(content=user_message),
    ]

    return _generate_with_validation_retries(
        client=client,
        model=DEFAULT_MODEL,
        messages=messages,
        label="slide components",
        output_model=SlideComponents,
        validation_retries=validation_retries,
        retry_loop=retry_loop,
        response_file=response_file,
    )


GENERATE_SLIDE_LAYOUTS_PROMPT = """
Create slide layout for each slide using the available slide components.

# Steps
1. Go through each slide and identify the shapes present in it.
2. Go through available components and find the ones that match the shapes present in the slide.
3. Create a layout for each slide using the matching components.

# Slide Layout Rules
- Must only use the available slide components to create a layout.
- Slide layout must be 1280x720.

# Slide Component Rules
- Modify the position and size of component to create a layout that matches the slide.

# Output Rules
- Return raw JSON only. Do not include markdown fences, comments, explanations, or any text before or after the JSON object.
"""


def generate_slide_layouts(
    presentation: dict,
    components: dict[str, Any],
    validation_retries: int = DEFAULT_VALIDATION_RETRIES,
    retry_loop: bool = True,
    response_file: str | None = None,
):

    client = _create_google_client()

    slide_count = len(presentation.get("slides", []))
    component_count = len(components.get("components", []))
    print(
        f"LLM: preparing to generate layouts for {slide_count} slides using {component_count} components.",
        flush=True,
    )
    user_message = f"- Presentation:\n{presentation}\n\n- Available Slide Components:\n{components}"
    messages = [
        SystemMessage(content=GENERATE_SLIDE_LAYOUTS_PROMPT),
        UserMessage(content=user_message),
    ]

    return _generate_with_validation_retries(
        client=client,
        model=DEFAULT_MODEL,
        messages=messages,
        label="slide layouts",
        output_model=SlideLayouts,
        validation_retries=validation_retries,
        retry_loop=retry_loop,
        response_file=response_file,
    )


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
) -> dict[str, Any]:
    if not retry_loop:
        return _generate_one_shot(
            client=client,
            model=model,
            messages=messages,
            label=label,
            output_model=output_model,
            response_file=response_file,
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
                reasoning_effort=DEFAULT_REASONING_EFFORT,
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
) -> dict[str, Any]:
    print(f"LLM: generating {label} once with {model}.", flush=True)
    response = client.generate(
        model=model,
        messages=messages,
        response_format=TextResponse(),
        reasoning_effort=DEFAULT_REASONING_EFFORT,
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


def _create_google_client() -> OpenAIClient:
    return OpenAIClient(
        config=OpenAIClientConfig(
            api_key=SETTINGS.google_api_key,
            base_url=SETTINGS.google_openai_base_url,
            api_type=OpenAIApiType.COMPLETIONS,
        )
    )


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
