"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Arc,
  Circle,
  Ellipse,
  Group,
  Image as KonvaImage,
  Line,
  Rect,
  Text,
} from "react-konva";
import type {
  Alignment,
  BorderRadius,
  ChartElement,
  Font,
  ImageElement,
  Padding,
  SlideElement,
  TextElement,
} from "@/types/elements";

const DEFAULT_FONT_FAMILY = "Arial";
const DEFAULT_FONT_SIZE = 16;
const DEFAULT_FONT_COLOR = "#111111";
const DEFAULT_FONT: Font = {
  family: DEFAULT_FONT_FAMILY,
  size: DEFAULT_FONT_SIZE,
  color: DEFAULT_FONT_COLOR,
};

export type RenderMode = "absolute" | "flow";

interface Frame {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type ElementRendererProps =
  | {
      element: SlideElement;
      mode?: RenderMode;
      frame?: Frame;
      showMissingImageMarkers?: boolean;
    }
  | (SlideElement & {
      mode?: RenderMode;
      frame?: Frame;
      showMissingImageMarkers?: boolean;
    });

export default function ElementRenderer(props: ElementRendererProps) {
  const {
    element,
    mode = "absolute",
    frame,
    showMissingImageMarkers = true,
  } = normalizeElementRendererProps(props);

  switch (element.type) {
    case "text":
      return <TextElementView element={element} frame={elementFrame(element, mode, frame)} />;
    case "container":
      return (
        <ContainerElementView
          element={element}
          frame={elementFrame(element, mode, frame)}
          showMissingImageMarkers={showMissingImageMarkers}
        />
      );
    case "image":
      return (
        <ImageElementView
          element={element}
          frame={elementFrame(element, mode, frame)}
          showMissingImageMarkers={showMissingImageMarkers}
        />
      );
    case "text-list":
      return (
        <TextListElementView
          element={element}
          frame={elementFrame(element, mode, frame)}
        />
      );
    case "table":
      return (
        <TableElementView
          element={element}
          frame={elementFrame(element, mode, frame)}
        />
      );
    case "rectangle":
      return <RectangleElementView element={element} frame={elementFrame(element, mode, frame)} />;
    case "ellipse":
      return <EllipseElementView element={element} frame={elementFrame(element, mode, frame)} />;
    case "line":
      return <LineElementView element={element} frame={elementFrame(element, mode, frame)} />;
    case "chart":
      return <ChartElementView element={element} frame={elementFrame(element, mode, frame)} />;
    case "flex":
      return (
        <FlexElementView
          element={element}
          frame={elementFrame(element, mode, frame)}
          showMissingImageMarkers={showMissingImageMarkers}
        />
      );
    case "grid":
      return (
        <GridElementView
          element={element}
          frame={elementFrame(element, mode, frame)}
          showMissingImageMarkers={showMissingImageMarkers}
        />
      );
    case "list-view":
      return (
        <ListViewElementView
          element={element}
          frame={elementFrame(element, mode, frame)}
          showMissingImageMarkers={showMissingImageMarkers}
        />
      );
    case "grid-view":
      return (
        <GridViewElementView
          element={element}
          frame={elementFrame(element, mode, frame)}
          showMissingImageMarkers={showMissingImageMarkers}
        />
      );
    case "stack":
      return (
        <StackElementView
          element={element}
          frame={elementFrame(element, mode, frame)}
          showMissingImageMarkers={showMissingImageMarkers}
        />
      );
  }
}

export { ElementRenderer };

function TextElementView({
  element,
  frame,
}: {
  element: Extract<SlideElement, { type: "text" }>;
  frame: Frame;
}) {
  const font = element.font ?? DEFAULT_FONT;
  const text = textElementContent(element, font);

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      {element.fill ? (
        <Rect
          width={frame.width}
          height={frame.height}
          fill={colorWithOpacity(element.fill.color, element.fill.opacity)}
        />
      ) : null}
      <Text
        width={frame.width}
        height={frame.height}
        text={text}
        fill={cssColor(font.color ?? DEFAULT_FONT_COLOR)}
        fontFamily={font.family ?? DEFAULT_FONT_FAMILY}
        fontSize={font.size ?? DEFAULT_FONT_SIZE}
        fontStyle={`${font.italic ? "italic" : "normal"} ${
          font.bold ? "bold" : "normal"
        }`}
        lineHeight={lineHeightMultiplier(font)}
        letterSpacing={font.letterSpacing ?? 0}
        align={element.alignment?.horizontal ?? "left"}
        verticalAlign={verticalTextAlignment(element.alignment)}
        wrap={font.wrap === "none" ? "none" : font.wrap === "char" ? "char" : "word"}
        ellipsis={font.ellipsis ?? false}
        stroke={cssColor(element.stroke?.color)}
        strokeWidth={element.stroke?.width ?? 0}
        shadowColor={cssColor(element.shadow?.color ?? undefined)}
        shadowBlur={element.shadow?.blur ?? 0}
        shadowOpacity={element.shadow?.opacity ?? 0}
        shadowOffsetX={element.shadow?.offsetX ?? 0}
        shadowOffsetY={element.shadow?.offsetY ?? 0}
      />
    </Group>
  );
}

function ContainerElementView({
  element,
  frame,
  showMissingImageMarkers,
}: {
  element: Extract<SlideElement, { type: "container" }>;
  frame: Frame;
  showMissingImageMarkers: boolean;
}) {
  const childFrame = childFlowFrame(frame, element.padding);
  const childMode =
    element.child && hasExplicitFrame(element.child) ? "absolute" : "flow";

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      <Rect
        width={frame.width}
        height={frame.height}
        fill={colorWithOpacity(element.fill?.color, element.fill?.opacity)}
        stroke={colorWithOpacity(element.stroke?.color, element.stroke?.opacity)}
        strokeWidth={element.stroke?.width ?? 0}
        dash={element.stroke?.dash ?? undefined}
        cornerRadius={cornerRadius(element.borderRadius)}
        shadowColor={cssColor(element.shadow?.color ?? undefined)}
        shadowBlur={element.shadow?.blur ?? 0}
        shadowOpacity={element.shadow?.opacity ?? 0}
        shadowOffsetX={element.shadow?.offsetX ?? 0}
        shadowOffsetY={element.shadow?.offsetY ?? 0}
      />
      {element.child ? (
        <ElementRenderer
          element={element.child}
          mode={childMode}
          frame={childMode === "flow" ? childFrame : undefined}
          showMissingImageMarkers={showMissingImageMarkers}
        />
      ) : null}
    </Group>
  );
}

function ImageElementView({
  element,
  frame,
  showMissingImageMarkers,
}: {
  element: ImageElement;
  frame: Frame;
  showMissingImageMarkers: boolean;
}) {
  const src = imageSource(element.data);
  const image = useLoadedImage(src);
  const imageFrame = useMemo(
    () =>
      image
        ? fittedImageFrame(
            image.width,
            image.height,
            frame.width,
            frame.height,
            element.fit ?? (element.is_icon ? "contain" : "cover"),
          )
        : null,
    [element.fit, element.is_icon, frame.height, frame.width, image],
  );

  if (!src || !image || !imageFrame) {
    if (!showMissingImageMarkers) {
      return null;
    }

    return (
      <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
        <Rect
          width={frame.width}
          height={frame.height}
          fill="rgba(241, 245, 249, 0.75)"
          stroke="#94a3b8"
          strokeWidth={2}
          cornerRadius={cornerRadius(element.borderRadius)}
        />
        <Text
          x={8}
          y={8}
          width={Math.max(frame.width - 16, 0)}
          text={`Missing image: ${element.name ?? "Image"}`}
          fill="#475569"
          fontFamily="Arial"
          fontSize={12}
          ellipsis
        />
      </Group>
    );
  }

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      <KonvaImage
        image={image}
        x={imageFrame.x}
        y={imageFrame.y}
        width={imageFrame.width}
        height={imageFrame.height}
      />
    </Group>
  );
}

function TextListElementView({
  element,
  frame,
}: {
  element: Extract<SlideElement, { type: "text-list" }>;
  frame: Frame;
}) {
  const font = element.font ?? DEFAULT_FONT;
  const fontSize = font.size ?? DEFAULT_FONT_SIZE;
  const lineHeight = font.lineHeight ?? fontSize * 1.35;
  const markerWidth = element.marker === "none" ? 0 : fontSize * 1.4;

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      {textListItems(element).map((item, index) => (
        <Group key={`text-list-item-${index}`} y={index * lineHeight}>
          {element.marker === "none" ? null : (
            <Text
              width={markerWidth}
              height={lineHeight}
              text={element.marker === "number" ? `${index + 1}.` : "•"}
              fill={cssColor(font.color ?? DEFAULT_FONT_COLOR)}
              fontFamily={font.family ?? DEFAULT_FONT_FAMILY}
              fontSize={fontSize}
              fontStyle={font.bold ? "bold" : "normal"}
            />
          )}
          <Text
            x={markerWidth}
            width={Math.max(frame.width - markerWidth, 0)}
            height={lineHeight}
            text={item.text}
            fill={cssColor(font.color ?? DEFAULT_FONT_COLOR)}
            fontFamily={font.family ?? DEFAULT_FONT_FAMILY}
            fontSize={fontSize}
            fontStyle={font.bold ? "bold" : "normal"}
            lineHeight={lineHeightMultiplier(font)}
            ellipsis
          />
        </Group>
      ))}
    </Group>
  );
}

function TableElementView({
  element,
  frame,
}: {
  element: Extract<SlideElement, { type: "table" }>;
  frame: Frame;
}) {
  const rows = [element.columns, ...element.rows].filter((row) => row.length > 0);
  const tableRows = rows.length > 0 ? rows : [[{}]];
  const columnCount = Math.max(...tableRows.map((row) => row.length), 1);
  const rowCount = Math.max(tableRows.length, 1);
  const cellWidth = frame.width / columnCount;
  const cellHeight = frame.height / rowCount;

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      {tableRows.flatMap((row, rowIndex) =>
        Array.from({ length: columnCount }, (_, cellIndex) => {
          const cell = row[cellIndex] ?? {};

          return (
            <Group
              key={`table-cell-${rowIndex}-${cellIndex}`}
              x={cellIndex * cellWidth}
              y={rowIndex * cellHeight}
            >
              <Rect
                width={cellWidth}
                height={cellHeight}
                fill={colorWithOpacity(cell.fill?.color, cell.fill?.opacity) ?? "#ffffff"}
                stroke={colorWithOpacity(cell.stroke?.color, cell.stroke?.opacity) ?? "#dddddd"}
                strokeWidth={cell.stroke?.width ?? 1}
              />
              <Text
                x={8}
                y={6}
                width={Math.max(cellWidth - 16, 0)}
                height={Math.max(cellHeight - 12, 0)}
                text={cell.text ?? textPlaceholder(DEFAULT_FONT, cell.minLength, cell.maxLength)}
                fill="#111111"
                fontFamily="Arial"
                fontSize={14}
                verticalAlign="middle"
                ellipsis
              />
            </Group>
          );
        }),
      )}
    </Group>
  );
}

function RectangleElementView({
  element,
  frame,
}: {
  element: Extract<SlideElement, { type: "rectangle" }>;
  frame: Frame;
}) {
  return (
    <Rect
      x={frame.x}
      y={frame.y}
      width={frame.width}
      height={frame.height}
      rotation={element.rotation ?? 0}
      fill={colorWithOpacity(element.fill?.color, element.fill?.opacity)}
      stroke={colorWithOpacity(element.stroke?.color, element.stroke?.opacity)}
      strokeWidth={element.stroke?.width ?? 0}
      dash={element.stroke?.dash ?? undefined}
      cornerRadius={cornerRadius(element.borderRadius)}
      shadowColor={cssColor(element.shadow?.color ?? undefined)}
      shadowBlur={element.shadow?.blur ?? 0}
      shadowOpacity={element.shadow?.opacity ?? 0}
      shadowOffsetX={element.shadow?.offsetX ?? 0}
      shadowOffsetY={element.shadow?.offsetY ?? 0}
    />
  );
}

function EllipseElementView({
  element,
  frame,
}: {
  element: Extract<SlideElement, { type: "ellipse" }>;
  frame: Frame;
}) {
  return (
    <Ellipse
      x={frame.x + frame.width / 2}
      y={frame.y + frame.height / 2}
      radiusX={frame.width / 2}
      radiusY={frame.height / 2}
      rotation={element.rotation ?? 0}
      fill={colorWithOpacity(element.fill?.color, element.fill?.opacity)}
      stroke={colorWithOpacity(element.stroke?.color, element.stroke?.opacity)}
      strokeWidth={element.stroke?.width ?? 0}
      shadowColor={cssColor(element.shadow?.color ?? undefined)}
      shadowBlur={element.shadow?.blur ?? 0}
      shadowOpacity={element.shadow?.opacity ?? 0}
      shadowOffsetX={element.shadow?.offsetX ?? 0}
      shadowOffsetY={element.shadow?.offsetY ?? 0}
    />
  );
}

function LineElementView({
  element,
  frame,
}: {
  element: Extract<SlideElement, { type: "line" }>;
  frame: Frame;
}) {
  return (
    <Line
      x={frame.x}
      y={frame.y}
      points={linePoints(frame.width, frame.height, element.stroke.width)}
      rotation={element.rotation ?? 0}
      stroke={cssColor(element.stroke.color) ?? "#000000"}
      strokeWidth={element.stroke.width}
      dash={element.stroke.dash ?? undefined}
      opacity={element.stroke.opacity ?? 1}
      lineCap="round"
      shadowColor={cssColor(element.shadow?.color ?? undefined)}
      shadowBlur={element.shadow?.blur ?? 0}
      shadowOpacity={element.shadow?.opacity ?? 0}
      shadowOffsetX={element.shadow?.offsetX ?? 0}
      shadowOffsetY={element.shadow?.offsetY ?? 0}
    />
  );
}

function ChartElementView({
  element,
  frame,
}: {
  element: ChartElement;
  frame: Frame;
}) {
  const titleHeight = element.title ? 28 : 0;

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      {element.title ? (
        <Text
          width={frame.width}
          height={titleHeight}
          text={element.title}
          fill={cssColor(element.labelColor) ?? "#222222"}
          fontFamily="Arial"
          fontSize={14}
          fontStyle="bold"
          ellipsis
        />
      ) : null}
      <Group y={titleHeight}>
        {element.chartType === "donut"
          ? renderDonutChart(element, frame.width, Math.max(frame.height - titleHeight, 1))
          : renderCartesianChart(
              element,
              frame.width,
              Math.max(frame.height - titleHeight, 1),
            )}
      </Group>
    </Group>
  );
}

function FlexElementView({
  element,
  frame,
  showMissingImageMarkers,
}: {
  element: Extract<SlideElement, { type: "flex" }>;
  frame: Frame;
  showMissingImageMarkers: boolean;
}) {
  const childFrames = flexChildFrames(element.children, frame, element.direction, {
    gap: element.gap,
    columnGap: element.columnGap,
    rowGap: element.rowGap,
  });

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      {element.children.map((child, index) => {
        const isDetached = isDetachedFlowElement(child);

        return (
          <ElementRenderer
            key={`flex-child-${index}`}
            element={child}
            mode={isDetached ? "absolute" : "flow"}
            frame={childFrames[index]}
            showMissingImageMarkers={showMissingImageMarkers}
          />
        );
      })}
    </Group>
  );
}

function GridElementView({
  element,
  frame,
  showMissingImageMarkers,
}: {
  element: Extract<SlideElement, { type: "grid" }>;
  frame: Frame;
  showMissingImageMarkers: boolean;
}) {
  const childFrames = gridChildFrames(
    element.children.length,
    frame,
    element.columns,
    element.rows,
    {
      gap: element.gap,
      columnGap: element.columnGap,
      rowGap: element.rowGap,
    },
  );

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      {element.children.map((child, index) => {
        const isDetached = isDetachedFlowElement(child);

        return (
          <ElementRenderer
            key={`grid-child-${index}`}
            element={child}
            mode={isDetached ? "absolute" : "flow"}
            frame={childFrames[index]}
            showMissingImageMarkers={showMissingImageMarkers}
          />
        );
      })}
    </Group>
  );
}

function ListViewElementView({
  element,
  frame,
  showMissingImageMarkers,
}: {
  element: Extract<SlideElement, { type: "list-view" }>;
  frame: Frame;
  showMissingImageMarkers: boolean;
}) {
  const count = Math.max(0, Math.floor(element.count));
  const children = Array.from({ length: count }, () => element.item);
  const childFrames = flexChildFrames(children, frame, element.direction ?? "column", {
    gap: element.gap,
    columnGap: element.columnGap,
    rowGap: element.rowGap,
  });

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      {children.map((child, index) => {
        const childFrame = childFrames[index];

        if (isDetachedFlowElement(child)) {
          return (
            <Group
              key={`list-view-item-${index}`}
              x={childFrame.x}
              y={childFrame.y}
            >
              <ElementRenderer
                element={child}
                mode="absolute"
                frame={{
                  x: 0,
                  y: 0,
                  width: childFrame.width,
                  height: childFrame.height,
                }}
                showMissingImageMarkers={showMissingImageMarkers}
              />
            </Group>
          );
        }

        return (
          <ElementRenderer
            key={`list-view-item-${index}`}
            element={child}
            mode="flow"
            frame={childFrame}
            showMissingImageMarkers={showMissingImageMarkers}
          />
        );
      })}
    </Group>
  );
}

function GridViewElementView({
  element,
  frame,
  showMissingImageMarkers,
}: {
  element: Extract<SlideElement, { type: "grid-view" }>;
  frame: Frame;
  showMissingImageMarkers: boolean;
}) {
  const count = Math.max(0, Math.floor(element.count));
  const children = Array.from({ length: count }, () => element.item);
  const childFrames = gridChildFrames(count, frame, element.columns, element.rows, {
    gap: element.gap,
    columnGap: element.columnGap,
    rowGap: element.rowGap,
  });

  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      {children.map((child, index) => {
        const childFrame = childFrames[index];

        if (isDetachedFlowElement(child)) {
          return (
            <Group
              key={`grid-view-item-${index}`}
              x={childFrame.x}
              y={childFrame.y}
            >
              <ElementRenderer
                element={child}
                mode="absolute"
                frame={{
                  x: 0,
                  y: 0,
                  width: childFrame.width,
                  height: childFrame.height,
                }}
                showMissingImageMarkers={showMissingImageMarkers}
              />
            </Group>
          );
        }

        return (
          <ElementRenderer
            key={`grid-view-item-${index}`}
            element={child}
            mode="flow"
            frame={childFrame}
            showMissingImageMarkers={showMissingImageMarkers}
          />
        );
      })}
    </Group>
  );
}

function StackElementView({
  element,
  frame,
  showMissingImageMarkers,
}: {
  element: Extract<SlideElement, { type: "stack" }>;
  frame: Frame;
  showMissingImageMarkers: boolean;
}) {
  return (
    <Group x={frame.x} y={frame.y} rotation={element.rotation ?? 0}>
      {element.children.map((child, index) => (
        <ElementRenderer
          key={`stack-child-${index}`}
          element={child}
          mode="absolute"
          showMissingImageMarkers={showMissingImageMarkers}
        />
      ))}
    </Group>
  );
}

function renderCartesianChart(element: ChartElement, width: number, height: number) {
  const data = element.data ?? [];
  const maxValue = Math.max(...data.map((datum) => datum.value), 1);
  const axisColor = cssColor(element.axisColor) ?? "#999999";
  const fallbackColor = cssColor(element.color) ?? "#3b82f6";
  const plot = {
    x: 28,
    y: 12,
    width: Math.max(width - 42, 1),
    height: Math.max(height - 32, 1),
  };

  if (element.chartType === "line") {
    return (
      <Group>
        {renderChartAxes(plot, axisColor)}
        <Line
          points={data.flatMap((datum, index) => [
            plot.x +
              (data.length <= 1 ? plot.width / 2 : (index / (data.length - 1)) * plot.width),
            plot.y + plot.height - (Math.max(datum.value, 0) / maxValue) * plot.height,
          ])}
          stroke={fallbackColor}
          strokeWidth={3}
          lineJoin="round"
          lineCap="round"
        />
      </Group>
    );
  }

  const slotWidth = plot.width / Math.max(data.length, 1);
  const barWidth = slotWidth * 0.62;

  return (
    <Group>
      {renderChartAxes(plot, axisColor)}
      {data.map((datum, index) => {
        const barHeight = (Math.max(datum.value, 0) / maxValue) * plot.height;

        return (
          <Rect
            key={`${datum.label}-${index}`}
            x={plot.x + index * slotWidth + (slotWidth - barWidth) / 2}
            y={plot.y + plot.height - barHeight}
            width={barWidth}
            height={barHeight}
            fill={cssColor(datum.color) ?? fallbackColor}
          />
        );
      })}
    </Group>
  );
}

function renderChartAxes(
  plot: { x: number; y: number; width: number; height: number },
  axisColor: string,
) {
  return (
    <>
      <Line
        points={[plot.x, plot.y + plot.height, plot.x + plot.width, plot.y + plot.height]}
        stroke={axisColor}
        strokeWidth={1}
      />
      <Line
        points={[plot.x, plot.y, plot.x, plot.y + plot.height]}
        stroke={axisColor}
        strokeWidth={1}
      />
    </>
  );
}

function renderDonutChart(element: ChartElement, width: number, height: number) {
  const total = element.data.reduce(
    (sum, datum) => sum + Math.max(datum.value, 0),
    0,
  );
  const radius = Math.max(Math.min(width, height) / 2 - 4, 1);
  const innerRadius = radius * 0.58;
  const fallbackColor = cssColor(element.color) ?? "#3b82f6";
  let cursor = -90;

  return (
    <Group x={width / 2} y={height / 2}>
      {element.data.map((datum, index) => {
        const angle = total > 0 ? (Math.max(datum.value, 0) / total) * 360 : 360;
        const rotation = cursor;
        cursor += angle;

        return (
          <Arc
            key={`${datum.label}-${index}`}
            innerRadius={innerRadius}
            outerRadius={radius}
            angle={angle}
            rotation={rotation}
            fill={cssColor(datum.color) ?? fallbackColor}
          />
        );
      })}
      <Circle radius={innerRadius} fill="#ffffff" />
    </Group>
  );
}

function normalizeElementRendererProps(props: ElementRendererProps) {
  if ("element" in props) {
    return props;
  }

  const { mode, frame, showMissingImageMarkers, ...element } = props;

  return {
    element,
    mode,
    frame,
    showMissingImageMarkers,
  };
}

function elementFrame(
  element: SlideElement,
  mode: RenderMode,
  flowFrame?: Frame,
): Frame {
  if (mode === "flow" && flowFrame) {
    return flowFrame;
  }

  const position = elementPosition(element);
  const size = elementSize(element);

  return {
    x: position?.x ?? 0,
    y: position?.y ?? 0,
    width: size?.width ?? flowFrame?.width ?? 0,
    height: size?.height ?? flowFrame?.height ?? 0,
  };
}

function elementPosition(element: SlideElement) {
  return "position" in element ? element.position ?? null : null;
}

function elementSize(element: SlideElement) {
  return "size" in element ? element.size ?? null : null;
}

function hasExplicitFrame(element: SlideElement) {
  return elementPosition(element) != null || elementSize(element) != null;
}

function isDetachedFlowElement(element: SlideElement) {
  return element.fixed === true && elementPosition(element) != null;
}

function childFlowFrame(frame: Frame, padding?: Padding | null): Frame {
  return {
    x: padding?.left ?? 0,
    y: padding?.top ?? 0,
    width: Math.max(frame.width - (padding?.left ?? 0) - (padding?.right ?? 0), 0),
    height: Math.max(frame.height - (padding?.top ?? 0) - (padding?.bottom ?? 0), 0),
  };
}

function flexChildFrames(
  children: SlideElement[],
  frame: Frame,
  direction: "row" | "column",
  gaps: { gap?: number | null; columnGap?: number | null; rowGap?: number | null },
) {
  const count = children.length;
  const gap = direction === "row" ? gaps.columnGap ?? gaps.gap ?? 0 : gaps.rowGap ?? gaps.gap ?? 0;
  const totalGap = Math.max(count - 1, 0) * gap;
  const fixedMain = children.reduce((sum, child) => {
    const size = elementSize(child);
    return sum + (direction === "row" ? size?.width ?? 0 : size?.height ?? 0);
  }, 0);
  const flexibleCount = children.filter((child) => {
    const size = elementSize(child);
    return direction === "row" ? size?.width == null : size?.height == null;
  }).length;
  const availableMain = direction === "row" ? frame.width : frame.height;
  const flexibleMain =
    flexibleCount > 0
      ? Math.max((availableMain - fixedMain - totalGap) / flexibleCount, 0)
      : 0;
  let cursor = 0;

  return children.map((child) => {
    const size = elementSize(child);
    const width =
      direction === "row" ? size?.width ?? flexibleMain : size?.width ?? frame.width;
    const height =
      direction === "column" ? size?.height ?? flexibleMain : size?.height ?? frame.height;
    const childFrame = {
      x: direction === "row" ? cursor : 0,
      y: direction === "column" ? cursor : 0,
      width,
      height,
    };

    cursor += (direction === "row" ? width : height) + gap;
    return childFrame;
  });
}

function gridChildFrames(
  count: number,
  frame: Frame,
  columns: number,
  rows: number | null | undefined,
  gaps: { gap?: number | null; columnGap?: number | null; rowGap?: number | null },
) {
  const columnCount = Math.max(columns, 1);
  const rowCount = Math.max(rows ?? 0, Math.ceil(count / columnCount), 1);
  const columnGap = gaps.columnGap ?? gaps.gap ?? 0;
  const rowGap = gaps.rowGap ?? gaps.gap ?? 0;
  const cellWidth = Math.max((frame.width - columnGap * (columnCount - 1)) / columnCount, 0);
  const cellHeight = Math.max((frame.height - rowGap * (rowCount - 1)) / rowCount, 0);

  return Array.from({ length: count }, (_, index) => ({
    x: (index % columnCount) * (cellWidth + columnGap),
    y: Math.floor(index / columnCount) * (cellHeight + rowGap),
    width: cellWidth,
    height: cellHeight,
  }));
}

function textElementContent(element: TextElement, baseFont: Font) {
  const runs = element.runs?.filter((run) => run.text.length > 0);
  const legacyText = (element as TextElement & { text?: string | null }).text;

  return runs?.length
    ? runs.map((run) => run.text).join("")
    : legacyText ?? textPlaceholder(baseFont, element.minLength, element.maxLength);
}

function textListItems(
  element: Extract<SlideElement, { type: "text-list" }>,
) {
  if (element.items?.length) {
    return element.items;
  }

  const count = Math.max(element.minItems ?? 0, 1);

  return Array.from({ length: count }, () => ({
    type: "text" as const,
    text: textPlaceholder(
      element.font ?? DEFAULT_FONT,
      element.minItemLength,
      element.maxItemLength,
    ),
  }));
}

function textPlaceholder(
  font: Font,
  minLength?: number | null,
  maxLength?: number | null,
) {
  if ((font.size ?? DEFAULT_FONT_SIZE) >= 32) {
    return "Sample heading";
  }

  if ((minLength ?? 0) >= 40 || (maxLength ?? 0) >= 160) {
    return "Sample body copy showing where generated text will appear in this layout.";
  }

  return "Sample text";
}

function lineHeightMultiplier(font: Font) {
  if (!font.lineHeight || !font.size) {
    return 1;
  }

  return font.lineHeight / font.size;
}

function verticalTextAlignment(alignment?: Alignment | null) {
  switch (alignment?.vertical) {
    case "middle":
      return "middle";
    case "bottom":
      return "bottom";
    case "top":
    default:
      return "top";
  }
}

function cornerRadius(radius?: BorderRadius | null) {
  return radius ? [radius.tl, radius.tr, radius.br, radius.bl] : undefined;
}

function linePoints(width: number, height: number, strokeWidth: number) {
  if (width <= strokeWidth * 1.5 && height > width) {
    return [width / 2, 0, width / 2, height];
  }

  if (height <= strokeWidth * 1.5 || width > height * 2) {
    return [0, height / 2, width, height / 2];
  }

  return [0, 0, width, height];
}

function useLoadedImage(src?: string) {
  const [loadedImage, setLoadedImage] = useState<{
    image: HTMLImageElement;
    src: string;
  } | null>(null);

  useEffect(() => {
    if (!src) {
      return;
    }

    let cancelled = false;
    const nextImage = new window.Image();
    nextImage.crossOrigin = "anonymous";
    nextImage.onload = () => {
      if (!cancelled) {
        setLoadedImage({ image: nextImage, src });
      }
    };
    nextImage.onerror = () => {
      if (!cancelled) {
        setLoadedImage(null);
      }
    };
    nextImage.src = src;

    return () => {
      cancelled = true;
    };
  }, [src]);

  if (!loadedImage || loadedImage.src !== src) {
    return null;
  }

  return loadedImage.image;
}

function fittedImageFrame(
  imageWidth: number,
  imageHeight: number,
  width: number,
  height: number,
  fit: "contain" | "cover" | "fill",
) {
  if (fit === "fill" || imageWidth <= 0 || imageHeight <= 0) {
    return { x: 0, y: 0, width, height };
  }

  const scale =
    fit === "cover"
      ? Math.max(width / imageWidth, height / imageHeight)
      : Math.min(width / imageWidth, height / imageHeight);
  const nextWidth = imageWidth * scale;
  const nextHeight = imageHeight * scale;

  return {
    x: (width - nextWidth) / 2,
    y: (height - nextHeight) / 2,
    width: nextWidth,
    height: nextHeight,
  };
}

function imageSource(data?: string | null) {
  if (!data || data === "icon_placeholder" || data === "image_placeholder") {
    return undefined;
  }

  if (isLocalFilePath(data)) {
    return undefined;
  }

  if (
    data.startsWith("data:") ||
    data.startsWith("/") ||
    data.startsWith("http://") ||
    data.startsWith("https://")
  ) {
    return data;
  }

  return `data:image/png;base64,${data}`;
}

function isLocalFilePath(data: string) {
  return (
    data.startsWith("file://") ||
    /^[a-zA-Z]:[\\/]/.test(data) ||
    /^\/(?:home|Users|tmp|private|var|mnt|opt)\//.test(data)
  );
}

function cssColor(color?: string | null) {
  if (!color) {
    return undefined;
  }

  if (/^[0-9a-fA-F]{3,8}$/.test(color)) {
    return `#${color}`;
  }

  return color;
}

function colorWithOpacity(color?: string | null, opacity?: number | null) {
  const normalizedColor = cssColor(color);

  if (!normalizedColor) {
    return undefined;
  }

  if (opacity == null) {
    return normalizedColor;
  }

  const alpha = clampOpacity(opacity);
  const rgba = hexToRgba(normalizedColor, alpha);

  if (rgba) {
    return rgba;
  }

  if (alpha === 1) {
    return normalizedColor;
  }

  return `color-mix(in srgb, ${normalizedColor} ${alpha * 100}%, transparent)`;
}

function hexToRgba(color: string, opacity: number) {
  const match = color.match(/^#([0-9a-fA-F]{3,8})$/);

  if (!match) {
    return undefined;
  }

  let hex = match[1];

  if (hex.length === 3 || hex.length === 4) {
    hex = hex
      .split("")
      .map((character) => character + character)
      .join("");
  }

  const r = Number.parseInt(hex.slice(0, 2), 16);
  const g = Number.parseInt(hex.slice(2, 4), 16);
  const b = Number.parseInt(hex.slice(4, 6), 16);
  const intrinsicAlpha =
    hex.length === 8 ? Number.parseInt(hex.slice(6, 8), 16) / 255 : 1;
  const alpha = clampOpacity(opacity * intrinsicAlpha);

  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function clampOpacity(opacity: number) {
  return Math.max(0, Math.min(opacity, 1));
}
