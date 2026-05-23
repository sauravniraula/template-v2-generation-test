"""Pydantic models matching the frontend slide element types."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional, TypeAlias, Union

from pydantic import BaseModel, Field


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
    family: str
    size: float
    color: str
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
    color: Optional[str] = None
    blur: Optional[float] = None
    opacity: Optional[float] = None
    offsetX: Optional[float] = None
    offsetY: Optional[float] = None


class RichTextRun(BaseModel):
    text: str
    font: Optional[Font] = None


class ChartDatum(BaseModel):
    label: str
    value: float
    color: Optional[str] = None


class TextListItem(BaseModel):
    type: Literal["text"]
    text: str


class RichTextListItem(BaseModel):
    type: Literal["rich-text"]
    runs: list[RichTextRun]


ListItem: TypeAlias = Annotated[
    Union[
        TextListItem,
        RichTextListItem,
    ],
    Field(discriminator="type"),
]


class Text(BaseModel):
    type: Literal["text"]
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    font: Font
    alignment: Optional[Alignment] = None
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    shadow: Optional[Shadow] = None
    text: Optional[str] = None

    # Schema
    maxLength: Optional[int] = None
    minLength: Optional[int] = None


class RichText(BaseModel):
    type: Literal["rich-text"]
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    font: Optional[Font] = None
    alignment: Optional[Alignment] = None
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    shadow: Optional[Shadow] = None
    runs: Optional[list[RichTextRun]] = None

    # Schema
    maxLength: Optional[int] = None
    minLength: Optional[int] = None


class Container(BaseModel):
    type: Literal["container"]
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


class Image(BaseModel):
    type: Literal["image"]
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    data: Optional[str] = None
    name: Optional[str] = None
    fit: Optional[ImageFit] = None
    is_icon: Optional[bool] = None


class List(BaseModel):
    type: Literal["list"]
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    font: Optional[Font] = None
    marker: Optional[Marker] = None
    items: Optional[list[ListItem]] = None

    # Schema
    maxItems: Optional[int] = None
    minItems: Optional[int] = None
    maxItemLength: Optional[int] = None
    minItemLength: Optional[int] = None


class TableCell(BaseModel):
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    text: Optional[str] = None

    # Schema
    maxLength: Optional[int] = None
    minLength: Optional[int] = None


class Table(BaseModel):
    type: Literal["table"]
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


class Rectangle(BaseModel):
    type: Literal["rectangle"]
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    borderRadius: Optional[BorderRadius] = None
    shadow: Optional[Shadow] = None


class Ellipse(BaseModel):
    type: Literal["ellipse"]
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    shadow: Optional[Shadow] = None


class Line(BaseModel):
    type: Literal["line"]
    position: Optional[Position] = None
    size: Optional[Size] = None
    rotation: Optional[float] = None
    stroke: Stroke
    shadow: Optional[Shadow] = None


class Chart(BaseModel):
    type: Literal["chart"]
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


class Grid(BaseModel):
    type: Literal["grid"]
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


class Stack(BaseModel):
    type: Literal["stack"]
    position: Position
    size: Size
    rotation: Optional[float] = None
    children: list[SlideElement]

    # Schema
    maxChildren: Optional[int] = None
    minChildren: Optional[int] = None


SlideElement: TypeAlias = Annotated[
    Union[
        Text,
        RichText,
        Container,
        Image,
        List,
        Table,
        Rectangle,
        Ellipse,
        Line,
        Chart,
        Flex,
        Grid,
        Stack,
    ],
    Field(discriminator="type"),
]


for _model in (Container, Flex, Grid, Stack):
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
    "List",
    "ListItem",
    "Marker",
    "Padding",
    "Position",
    "Rectangle",
    "RichText",
    "RichTextListItem",
    "RichTextRun",
    "Shadow",
    "Size",
    "SlideElement",
    "Stack",
    "Stroke",
    "Table",
    "TableCell",
    "Text",
    "TextListItem",
    "TextWrap",
    "VerticalAlignment",
]
