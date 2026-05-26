import json
import os
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from layout_normalizer import normalize_slide_layouts
from llm_models import SlideLayouts
from template import generate_slide_layouts

presentation_file = "assets/presentation.json"
layouts_file = "assets/layouts.json"
retry_loop = True


def read_json(file_path: str) -> Any:
    with open(file_path, "r") as f:
        return json.load(f)


def write_json(file_path: str, data: Any) -> None:
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_or_generate_json(
    file_path: str,
    generate: Callable[[], dict[str, Any]],
    normalize: Callable[[Any], Any] | None = None,
    output_model: type[BaseModel] | None = None,
) -> dict[str, Any]:
    if os.path.exists(file_path):
        print(f"Using existing {file_path}")
        original_data = read_json(file_path)
        data = original_data
        if normalize:
            data = normalize(data)
        try:
            validated = validate_with_model(data, output_model)
            if data != original_data:
                write_json(file_path, validated)
                print(f"Saved normalized {file_path}")
            return validated
        except ValidationError as exc:
            print(
                f"Existing {file_path} failed {output_model.__name__} validation with {exc.error_count()} errors."
            )
            if not retry_loop:
                raise
            print(f"Regenerating {file_path}")
            data = generate()
            if normalize:
                data = normalize(data)
            validated = validate_with_model(data, output_model)
            write_json(file_path, validated)
            return validated

    print(f"Generating {file_path}")
    data = generate()
    if normalize:
        data = normalize(data)
    validated = validate_with_model(data, output_model)
    write_json(file_path, validated)
    return validated


def validate_with_model(
    data: dict[str, Any],
    output_model: type[BaseModel] | None,
) -> dict[str, Any]:
    if output_model is None:
        return data

    return output_model.model_validate(data).model_dump(mode="json")


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


def normalize_layout_response(value: Any) -> Any:
    normalized = normalize_slide_layouts(normalize_description_keys(value))

    if isinstance(normalized, list):
        return {"layouts": normalized}

    return normalized


def main() -> None:
    presentation = read_json(presentation_file)

    load_or_generate_json(
        layouts_file,
        lambda: generate_slide_layouts(
            presentation,
            retry_loop=retry_loop,
            response_file=layouts_file,
        ),
        normalize=normalize_layout_response,
        output_model=SlideLayouts,
    )


if __name__ == "__main__":
    main()
