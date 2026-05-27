"""Pydantic models matching the frontend slide element types."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional, TypeAlias, Union

from pydantic import BaseModel, Field, model_validator


def _validate_min_max(
    min_value: int | None,
    max_value: int | None,
    *,
    min_name: str,
    max_name: str,
) -> None:
    if min_value is not None and max_value is not None and min_value > max_value:
        raise ValueError(f"{min_name} must be less than or equal to {max_name}")


def _validate_value_bounds(
    value: int,
    min_value: int | None,
    max_value: int | None,
    *,
    value_name: str,
    min_name: str,
    max_name: str,
) -> None:
    if min_value is not None and value < min_value:
        raise ValueError(f"{value_name} must be greater than or equal to {min_name}")

    if max_value is not None and value > max_value:
        raise ValueError(f"{value_name} must be less than or equal to {max_name}")


class HorizontalAlignment(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class VerticalAlignment(str, Enum):
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class LayoutAlignment(str, Enum):
    FLEX_START = "flex-start"
    FLEX_END = "flex-end"
    CENTER = "center"
    STRETCH = "stretch"


class TextWrap(str, Enum):
    WORD = "word"
    CHAR = "char"
    NONE = "none"


class Marker(str, Enum):
    BULLET = "bullet"
    NUMBER = "number"
    NONE = "none"


class FlexDirection(str, Enum):
    ROW = "row"
    COLUMN = "column"


class ImageFit(str, Enum):
    CONTAIN = "contain"
    COVER = "cover"
    FILL = "fill"


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    DONUT = "donut"


class Position(BaseModel):
    x: float
    y: float


class Size(BaseModel):
    width: float
    height: float


class Padding(BaseModel):
    top: float
    right: float
    bottom: float
    left: float


class Alignment(BaseModel):
    horizontal: Optional[HorizontalAlignment] = None
    vertical: Optional[VerticalAlignment] = None


class Font(BaseModel):
    size: float
    family: Optional[str] = None
    color: Optional[str] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    lineHeight: Optional[float] = None
    letterSpacing: Optional[float] = None
    wrap: Optional[TextWrap] = None
    ellipsis: Optional[bool] = None


class Fill(BaseModel):
    color: str
    opacity: Optional[float] = None


class Stroke(BaseModel):
    color: str
    opacity: Optional[float] = None
    width: float
    dash: Optional[list[float]] = None


class BorderRadius(BaseModel):
    tl: float
    tr: float
    bl: float
    br: float


class Shadow(BaseModel):
    color: str
    blur: Optional[float] = None
    opacity: Optional[float] = None
    offsetX: Optional[float] = None
    offsetY: Optional[float] = None


class ChartDatum(BaseModel):
    label: str
    value: float
    color: Optional[str] = None


class TextRun(BaseModel):
    text: str
    font: Optional[Font] = None


class TextListItem(BaseModel):
    type: Literal["text"]
    text: str


class Text(BaseModel):  # Konva Text
    type: Literal["text"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    font: Optional[Font] = None
    alignment: Optional[Alignment] = None
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    shadow: Optional[Shadow] = None
    runs: Optional[list[TextRun]] = None

    # Schema
    maxLength: Optional[int] = None
    minLength: Optional[int] = None

    @model_validator(mode="after")
    def validate_schema_bounds(self):
        _validate_min_max(
            self.minLength,
            self.maxLength,
            min_name="minLength",
            max_name="maxLength",
        )
        return self


class Container(BaseModel):  # Konva Group
    type: Literal["container"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    alignment: Optional[Alignment] = None
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    borderRadius: Optional[BorderRadius] = None
    shadow: Optional[Shadow] = None
    padding: Optional[Padding] = None
    child: Optional[SlideElement] = None


class Image(BaseModel):  # Konva Image
    type: Literal["image"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    data: Optional[str] = None
    name: Optional[str] = None
    fit: Optional[ImageFit] = None
    borderRadius: Optional[BorderRadius] = None
    is_icon: Optional[bool] = None


class TextList(BaseModel):  # Konva Group
    type: Literal["text-list"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    font: Optional[Font] = None
    marker: Optional[Marker] = None
    items: Optional[list[TextListItem]] = None

    # Schema
    maxItems: Optional[int] = None
    minItems: Optional[int] = None
    maxItemLength: Optional[int] = None
    minItemLength: Optional[int] = None

    @model_validator(mode="after")
    def validate_schema_bounds(self):
        _validate_min_max(
            self.minItems,
            self.maxItems,
            min_name="minItems",
            max_name="maxItems",
        )
        _validate_min_max(
            self.minItemLength,
            self.maxItemLength,
            min_name="minItemLength",
            max_name="maxItemLength",
        )
        return self


class TableCell(BaseModel):
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    text: Optional[str] = None

    # Schema
    maxLength: Optional[int] = None
    minLength: Optional[int] = None

    @model_validator(mode="after")
    def validate_schema_bounds(self):
        _validate_min_max(
            self.minLength,
            self.maxLength,
            min_name="minLength",
            max_name="maxLength",
        )
        return self


class Table(BaseModel):
    type: Literal["table"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    columns: list[TableCell]
    rows: list[list[TableCell]]

    # Schema
    maxColumns: Optional[int] = None
    minColumns: Optional[int] = None
    maxRows: Optional[int] = None
    minRows: Optional[int] = None

    @model_validator(mode="after")
    def validate_schema_bounds(self):
        _validate_min_max(
            self.minColumns,
            self.maxColumns,
            min_name="minColumns",
            max_name="maxColumns",
        )
        _validate_min_max(
            self.minRows,
            self.maxRows,
            min_name="minRows",
            max_name="maxRows",
        )
        return self


class Rectangle(BaseModel):
    type: Literal["rectangle"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    borderRadius: Optional[BorderRadius] = None
    shadow: Optional[Shadow] = None


class Ellipse(BaseModel):
    type: Literal["ellipse"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    shadow: Optional[Shadow] = None


class Line(BaseModel):
    type: Literal["line"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    stroke: Stroke
    shadow: Optional[Shadow] = None


class Chart(BaseModel):
    type: Literal["chart"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    chartType: ChartType
    data: list[ChartDatum]
    title: Optional[str] = None
    color: Optional[str] = None
    axisColor: Optional[str] = None
    labelColor: Optional[str] = None
    showValues: Optional[bool] = None


class Flex(BaseModel):
    type: Literal["flex"]
    fixed: bool
    position: Position
    size: Size
    rotation: Optional[float] = None
    direction: FlexDirection
    wrap: Optional[bool] = None
    alignItems: Optional[LayoutAlignment] = None
    justifyContent: Optional[LayoutAlignment] = None
    gap: Optional[float] = None
    columnGap: Optional[float] = None
    rowGap: Optional[float] = None
    children: list[SlideElement]

    # Schema
    maxChildren: Optional[int] = None
    minChildren: Optional[int] = None

    @model_validator(mode="after")
    def validate_schema_bounds(self):
        _validate_min_max(
            self.minChildren,
            self.maxChildren,
            min_name="minChildren",
            max_name="maxChildren",
        )
        return self


class Grid(BaseModel):
    type: Literal["grid"]
    fixed: bool
    position: Position
    size: Size
    rotation: Optional[float] = None
    columns: int
    rows: Optional[int] = None
    gap: Optional[float] = None
    columnGap: Optional[float] = None
    rowGap: Optional[float] = None
    alignItems: Optional[LayoutAlignment] = None
    justifyItems: Optional[LayoutAlignment] = None
    children: list[SlideElement]

    # Schema
    maxChildren: Optional[int] = None
    minChildren: Optional[int] = None

    @model_validator(mode="after")
    def validate_schema_bounds(self):
        _validate_min_max(
            self.minChildren,
            self.maxChildren,
            min_name="minChildren",
            max_name="maxChildren",
        )
        return self


class ListView(BaseModel):
    type: Literal["list-view"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    direction: Optional[FlexDirection] = None
    gap: Optional[float] = None
    columnGap: Optional[float] = None
    rowGap: Optional[float] = None
    alignItems: Optional[LayoutAlignment] = None
    justifyContent: Optional[LayoutAlignment] = None
    count: int
    item: SlideElement

    # Schema
    maxCount: Optional[int] = None
    minCount: Optional[int] = None

    @model_validator(mode="after")
    def validate_schema_bounds(self):
        _validate_min_max(
            self.minCount,
            self.maxCount,
            min_name="minCount",
            max_name="maxCount",
        )
        _validate_value_bounds(
            self.count,
            self.minCount,
            self.maxCount,
            value_name="count",
            min_name="minCount",
            max_name="maxCount",
        )
        return self


class GridView(BaseModel):
    type: Literal["grid-view"]
    fixed: bool
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    columns: int
    rows: Optional[int] = None
    gap: Optional[float] = None
    columnGap: Optional[float] = None
    rowGap: Optional[float] = None
    alignItems: Optional[LayoutAlignment] = None
    justifyItems: Optional[LayoutAlignment] = None
    count: int
    item: SlideElement

    # Schema
    maxCount: Optional[int] = None
    minCount: Optional[int] = None

    @model_validator(mode="after")
    def validate_schema_bounds(self):
        _validate_min_max(
            self.minCount,
            self.maxCount,
            min_name="minCount",
            max_name="maxCount",
        )
        _validate_value_bounds(
            self.count,
            self.minCount,
            self.maxCount,
            value_name="count",
            min_name="minCount",
            max_name="maxCount",
        )
        return self


class Group(BaseModel):
    type: Literal["group"]
    fixed: bool
    position: Position
    size: Size
    rotation: Optional[float] = None
    children: list[SlideElement]

    # Schema
    maxChildren: Optional[int] = None
    minChildren: Optional[int] = None

    @model_validator(mode="after")
    def validate_schema_bounds(self):
        _validate_min_max(
            self.minChildren,
            self.maxChildren,
            min_name="minChildren",
            max_name="maxChildren",
        )
        return self


SlideElement: TypeAlias = Annotated[
    Union[
        Text,
        Container,
        Image,
        TextList,
        Table,
        Rectangle,
        Ellipse,
        Line,
        Chart,
        Flex,
        Grid,
        ListView,
        GridView,
        Group,
    ],
    Field(discriminator="type"),
]


for _model in (Container, Flex, Grid, ListView, GridView, Group):
    _model.model_rebuild()


__all__ = [
    "Alignment",
    "BorderRadius",
    "Chart",
    "ChartDatum",
    "ChartType",
    "Container",
    "Ellipse",
    "Fill",
    "Flex",
    "FlexDirection",
    "Font",
    "Grid",
    "HorizontalAlignment",
    "Image",
    "ImageFit",
    "LayoutAlignment",
    "Line",
    "ListView",
    "Marker",
    "Padding",
    "Position",
    "Rectangle",
    "Shadow",
    "Size",
    "SlideElement",
    "Group",
    "Stroke",
    "Table",
    "TableCell",
    "Text",
    "TextList",
    "TextListItem",
    "TextRun",
    "TextWrap",
    "VerticalAlignment",
    "GridView",
]
