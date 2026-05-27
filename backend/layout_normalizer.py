from __future__ import annotations

from copy import deepcopy
from typing import Any


Bounds = dict[str, float]


def normalize_slide_layouts(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize_slide_layout(layout) for layout in value]

    if isinstance(value, dict) and isinstance(value.get("layouts"), list):
        normalized = deepcopy(value)
        normalized["layouts"] = [
            normalize_slide_layout(layout) for layout in normalized["layouts"]
        ]
        return normalized

    return value


def normalize_slide_layout(layout: Any) -> Any:
    if not isinstance(layout, dict) or not isinstance(layout.get("components"), list):
        return layout

    normalized = deepcopy(layout)
    normalized["components"] = [
        normalize_slide_component(component)
        for component in normalized.get("components", [])
    ]
    return normalized


def normalize_slide_component(component: Any) -> Any:
    if not isinstance(component, dict):
        return component

    normalized = deepcopy(component)
    elements = normalized.get("elements")

    if not isinstance(elements, list):
        return normalized

    bounds = _elements_bounds(elements)

    if bounds is None:
        normalized["position"] = normalized.get("position") or {"x": 0, "y": 0}
        normalized["size"] = normalized.get("size") or {"width": 0, "height": 0}
        return normalized

    component_position = _position(normalized.get("position")) or {"x": 0, "y": 0}
    elements_look_slide_local = _position(
        normalized.get("position")
    ) is not None and _positions_match(component_position, bounds)

    if normalized.get("position") is None or elements_look_slide_local:
        next_position = {"x": bounds["x"], "y": bounds["y"]}
    else:
        next_position = {
            "x": component_position["x"] + bounds["x"],
            "y": component_position["y"] + bounds["y"],
        }

    normalized["position"] = next_position
    normalized["size"] = {"width": bounds["width"], "height": bounds["height"]}
    normalized["elements"] = [
        _translate_element(element, -bounds["x"], -bounds["y"])
        for element in elements
    ]
    return normalized


def _elements_bounds(elements: list[Any]) -> Bounds | None:
    bounds: Bounds | None = None

    for element in elements:
        bounds = _union_bounds(bounds, _element_bounds(element))

    return bounds


def _element_bounds(element: Any) -> Bounds | None:
    if not isinstance(element, dict):
        return None

    position = _position(element.get("position")) or {"x": 0, "y": 0}
    size = _size(element.get("size"))

    if size is not None:
        return {
            "x": position["x"],
            "y": position["y"],
            "width": size["width"],
            "height": size["height"],
        }

    nested_bounds = _nested_element_bounds(element)

    if nested_bounds is None:
        return None

    return {
        "x": position["x"] + nested_bounds["x"],
        "y": position["y"] + nested_bounds["y"],
        "width": nested_bounds["width"],
        "height": nested_bounds["height"],
    }


def _nested_element_bounds(element: dict[str, Any]) -> Bounds | None:
    if element.get("type") == "container":
        return _element_bounds(element.get("child"))

    if element.get("type") in {"flex", "grid", "group"}:
        children = element.get("children")
        return _elements_bounds(children) if isinstance(children, list) else None

    if element.get("type") == "list-view":
        return _list_view_bounds(element)

    if element.get("type") == "grid-view":
        return _grid_view_bounds(element)

    return None


def _list_view_bounds(element: dict[str, Any]) -> Bounds | None:
    item_bounds = _element_bounds(element.get("item"))

    if item_bounds is None:
        return None

    count = _count(element.get("count"))

    if count == 0:
        return {**item_bounds, "width": 0, "height": 0}

    if element.get("direction") == "row":
        gap = _number(element.get("columnGap")) or _number(element.get("gap")) or 0

        return {
            "x": item_bounds["x"],
            "y": item_bounds["y"],
            "width": item_bounds["width"] * count + gap * (count - 1),
            "height": item_bounds["height"],
        }

    gap = _number(element.get("rowGap")) or _number(element.get("gap")) or 0

    return {
        "x": item_bounds["x"],
        "y": item_bounds["y"],
        "width": item_bounds["width"],
        "height": item_bounds["height"] * count + gap * (count - 1),
    }


def _grid_view_bounds(element: dict[str, Any]) -> Bounds | None:
    item_bounds = _element_bounds(element.get("item"))

    if item_bounds is None:
        return None

    count = _count(element.get("count"))

    if count == 0:
        return {**item_bounds, "width": 0, "height": 0}

    columns = max(_count(element.get("columns")), 1)
    rows = max(_count(element.get("rows")), -(-count // columns), 1)
    column_gap = _number(element.get("columnGap")) or _number(element.get("gap")) or 0
    row_gap = _number(element.get("rowGap")) or _number(element.get("gap")) or 0

    return {
        "x": item_bounds["x"],
        "y": item_bounds["y"],
        "width": item_bounds["width"] * columns + column_gap * (columns - 1),
        "height": item_bounds["height"] * rows + row_gap * (rows - 1),
    }


def _translate_element(element: Any, delta_x: float, delta_y: float) -> Any:
    if not isinstance(element, dict) or (delta_x == 0 and delta_y == 0):
        return element

    translated = deepcopy(element)
    position = _position(translated.get("position"))

    if position is not None:
        translated["position"] = {
            "x": position["x"] + delta_x,
            "y": position["y"] + delta_y,
        }
        return translated

    if translated.get("type") == "container" and translated.get("child") is not None:
        translated["child"] = _translate_element(translated["child"], delta_x, delta_y)
        return translated

    if translated.get("type") in {"flex", "grid", "group"} and isinstance(
        translated.get("children"), list
    ):
        translated["children"] = [
            _translate_element(child, delta_x, delta_y)
            for child in translated["children"]
        ]
        return translated

    if translated.get("type") in {"list-view", "grid-view"}:
        translated["item"] = _translate_element(
            translated.get("item"), delta_x, delta_y
        )

    return translated


def _position(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None

    x = value.get("x")
    y = value.get("y")

    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None

    return {"x": float(x), "y": float(y)}


def _size(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None

    width = value.get("width")
    height = value.get("height")

    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return None

    return {"width": float(width), "height": float(height)}


def _count(value: Any) -> int:
    if not isinstance(value, (int, float)):
        return 0

    return max(0, int(value))


def _number(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None

    return float(value)


def _union_bounds(first: Bounds | None, second: Bounds | None) -> Bounds | None:
    if first is None:
        return second

    if second is None:
        return first

    x = min(first["x"], second["x"])
    y = min(first["y"], second["y"])
    right = max(first["x"] + first["width"], second["x"] + second["width"])
    bottom = max(first["y"] + first["height"], second["y"] + second["height"])

    return {
        "x": x,
        "y": y,
        "width": right - x,
        "height": bottom - y,
    }


def _positions_match(position: dict[str, float], bounds: Bounds) -> bool:
    return _nearly_equal(position["x"], bounds["x"]) and _nearly_equal(
        position["y"], bounds["y"]
    )


def _nearly_equal(first: float, second: float) -> bool:
    return abs(first - second) <= 1
