export type Nullable<T> = T | null;

export type HorizontalAlignment = "left" | "center" | "right";
export type VerticalAlignment = "top" | "middle" | "bottom";
export type LayoutAlignment =
  | "flex-start"
  | "flex-end"
  | "center"
  | "stretch";
export type TextWrap = "word" | "char" | "none";
export type Marker = "bullet" | "number" | "none";
export type FlexDirection = "row" | "column";
export type ImageFit = "contain" | "cover" | "fill";
export type ChartType = "bar" | "line" | "donut";

export interface Position {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

export interface Padding {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface Alignment {
  horizontal?: Nullable<HorizontalAlignment>;
  vertical?: Nullable<VerticalAlignment>;
}

export interface Font {
  family?: Nullable<string>;
  size?: Nullable<number>;
  color?: Nullable<string>;
  bold?: Nullable<boolean>;
  italic?: Nullable<boolean>;
  lineHeight?: Nullable<number>;
  letterSpacing?: Nullable<number>;
  wrap?: Nullable<TextWrap>;
  ellipsis?: Nullable<boolean>;
}

export interface Fill {
  color: string;
  opacity?: Nullable<number>;
}

export interface Stroke {
  color: string;
  opacity?: Nullable<number>;
  width: number;
  dash?: Nullable<number[]>;
}

export interface BorderRadius {
  tl: number;
  tr: number;
  bl: number;
  br: number;
}

export interface Shadow {
  color?: Nullable<string>;
  blur?: Nullable<number>;
  opacity?: Nullable<number>;
  offsetX?: Nullable<number>;
  offsetY?: Nullable<number>;
}

export interface ChartDatum {
  label: string;
  value: number;
  color?: Nullable<string>;
}

export interface TextRun {
  text: string;
  font?: Nullable<Font>;
}

export interface TextListItem {
  type: "text";
  text: string;
}

export interface TextElement {
  type: "text";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  font?: Nullable<Font>;
  alignment?: Nullable<Alignment>;
  fill?: Nullable<Fill>;
  stroke?: Nullable<Stroke>;
  shadow?: Nullable<Shadow>;
  runs?: Nullable<TextRun[]>;

  // Schema
  maxLength?: Nullable<number>;
  minLength?: Nullable<number>;
}

export interface ContainerElement {
  type: "container";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  alignment?: Nullable<Alignment>;
  fill?: Nullable<Fill>;
  stroke?: Nullable<Stroke>;
  borderRadius?: Nullable<BorderRadius>;
  shadow?: Nullable<Shadow>;
  padding?: Nullable<Padding>;
  child?: Nullable<SlideElement>;
}

export interface ImageElement {
  type: "image";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  data?: Nullable<string>;
  name?: Nullable<string>;
  fit?: Nullable<ImageFit>;
  borderRadius?: Nullable<BorderRadius>;
  is_icon?: Nullable<boolean>;
}

export interface TextListElement {
  type: "text-list";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  font?: Nullable<Font>;
  marker?: Nullable<Marker>;
  items?: Nullable<TextListItem[]>;

  // Schema
  maxItems?: Nullable<number>;
  minItems?: Nullable<number>;
  maxItemLength?: Nullable<number>;
  minItemLength?: Nullable<number>;
}

export interface TableCell {
  fill?: Nullable<Fill>;
  stroke?: Nullable<Stroke>;
  text?: Nullable<string>;

  // Schema
  maxLength?: Nullable<number>;
  minLength?: Nullable<number>;
}

export interface TableElement {
  type: "table";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  columns: TableCell[];
  rows: TableCell[][];

  // Schema
  maxColumns?: Nullable<number>;
  minColumns?: Nullable<number>;
  maxRows?: Nullable<number>;
  minRows?: Nullable<number>;
}

export interface RectangleElement {
  type: "rectangle";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  fill?: Nullable<Fill>;
  stroke?: Nullable<Stroke>;
  borderRadius?: Nullable<BorderRadius>;
  shadow?: Nullable<Shadow>;
}

export interface EllipseElement {
  type: "ellipse";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  fill?: Nullable<Fill>;
  stroke?: Nullable<Stroke>;
  shadow?: Nullable<Shadow>;
}

export interface LineElement {
  type: "line";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  stroke: Stroke;
  shadow?: Nullable<Shadow>;
}

export interface ChartElement {
  type: "chart";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  chartType: ChartType;
  data: ChartDatum[];
  title?: Nullable<string>;
  color?: Nullable<string>;
  axisColor?: Nullable<string>;
  labelColor?: Nullable<string>;
  showValues?: Nullable<boolean>;
}

export interface FlexElement {
  type: "flex";
  fixed?: Nullable<boolean>;
  position: Position;
  size: Size;
  rotation?: Nullable<number>;
  direction: FlexDirection;
  wrap?: Nullable<boolean>;
  alignItems?: Nullable<LayoutAlignment>;
  justifyContent?: Nullable<LayoutAlignment>;
  gap?: Nullable<number>;
  columnGap?: Nullable<number>;
  rowGap?: Nullable<number>;
  children: SlideElement[];

  // Schema
  maxChildren?: Nullable<number>;
  minChildren?: Nullable<number>;
}

export interface GridElement {
  type: "grid";
  fixed?: Nullable<boolean>;
  position: Position;
  size: Size;
  rotation?: Nullable<number>;
  columns: number;
  rows?: Nullable<number>;
  gap?: Nullable<number>;
  columnGap?: Nullable<number>;
  rowGap?: Nullable<number>;
  alignItems?: Nullable<LayoutAlignment>;
  justifyItems?: Nullable<LayoutAlignment>;
  children: SlideElement[];

  // Schema
  maxChildren?: Nullable<number>;
  minChildren?: Nullable<number>;
}

export interface ListViewElement {
  type: "list-view";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  direction?: Nullable<FlexDirection>;
  gap?: Nullable<number>;
  columnGap?: Nullable<number>;
  rowGap?: Nullable<number>;
  alignItems?: Nullable<LayoutAlignment>;
  justifyContent?: Nullable<LayoutAlignment>;
  count: number;
  item: SlideElement;

  // Schema
  maxCount?: Nullable<number>;
  minCount?: Nullable<number>;
}

export interface GridViewElement {
  type: "grid-view";
  fixed?: Nullable<boolean>;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  rotation?: Nullable<number>;
  columns: number;
  rows?: Nullable<number>;
  gap?: Nullable<number>;
  columnGap?: Nullable<number>;
  rowGap?: Nullable<number>;
  alignItems?: Nullable<LayoutAlignment>;
  justifyItems?: Nullable<LayoutAlignment>;
  count: number;
  item: SlideElement;

  // Schema
  maxCount?: Nullable<number>;
  minCount?: Nullable<number>;
}

export interface StackElement {
  type: "stack";
  fixed?: Nullable<boolean>;
  position: Position;
  size: Size;
  rotation?: Nullable<number>;
  children: SlideElement[];

  // Schema
  maxChildren?: Nullable<number>;
  minChildren?: Nullable<number>;
}

export type SlideElement =
  | TextElement
  | ContainerElement
  | ImageElement
  | TextListElement
  | TableElement
  | RectangleElement
  | EllipseElement
  | LineElement
  | ChartElement
  | FlexElement
  | GridElement
  | ListViewElement
  | GridViewElement
  | StackElement;
