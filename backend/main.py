import json
import os
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from llm_models import SlideComponents, SlideLayouts
from template import generate_slide_components, generate_slide_layouts

presentation_file = "assets/presentation.json"
components_file = "assets/components.json"
layouts_file = "assets/layouts.json"
retry_loop = True


def read_json(file_path: str) -> Any:
    with open(file_path, "r") as f:
        return json.load(f)


def load_or_generate_json(
    file_path: str,
    generate: Callable[[], dict[str, Any]],
    normalize: Callable[[Any], Any] | None = None,
    output_model: type[BaseModel] | None = None,
) -> dict[str, Any]:
    if os.path.exists(file_path):
        print(f"Using existing {file_path}")
        data = read_json(file_path)
        if normalize:
            data = normalize(data)
        try:
            return validate_with_model(data, output_model)
        except ValidationError as exc:
            print(
                f"Existing {file_path} failed {output_model.__name__} validation with {exc.error_count()} errors."
            )
            if not retry_loop:
                raise
            print(f"Regenerating {file_path}")
            return validate_with_model(generate(), output_model)

    print(f"Generating {file_path}")
    return validate_with_model(generate(), output_model)


def validate_with_model(
    data: dict[str, Any],
    output_model: type[BaseModel] | None,
) -> dict[str, Any]:
    if output_model is None:
        return data

    return output_model.model_validate(data).model_dump(mode="json")


def normalize_layouts(data: Any) -> Any:
    if isinstance(data, list):
        data = {"layouts": data}

    return normalize_description_keys(data)


def normalize_description_keys(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize_description_keys(item) for item in value]

    if isinstance(value, dict):
        normalized = {
            key: normalize_description_keys(item) for key, item in value.items()
        }
        if "descritpion" in normalized and "description" not in normalized:
            normalized["description"] = normalized["descritpion"]
        return normalized

    return value


def main() -> None:
    presentation = read_json(presentation_file)

    components = load_or_generate_json(
        components_file,
        lambda: generate_slide_components(
            presentation,
            retry_loop=retry_loop,
            response_file=components_file,
        ),
        normalize=normalize_description_keys,
        output_model=SlideComponents,
    )

    load_or_generate_json(
        layouts_file,
        lambda: generate_slide_layouts(
            presentation,
            components,
            retry_loop=retry_loop,
            response_file=layouts_file,
        ),
        normalize=normalize_layouts,
        output_model=SlideLayouts,
    )


if __name__ == "__main__":
    main()
