/* eslint-disable @next/next/no-img-element */

import type { CSSProperties, ReactNode } from "react";
import type {
  Alignment,
  BorderRadius,
  ChartElement,
  Fill,
  Font,
  ImageElement,
  ListItem,
  Padding,
  RichTextRun,
  Shadow,
  SlideElement,
  Stroke,
} from "@/types/elements";
import type { SlideComponent } from "@/types/component";
import type { SlideLayout } from "@/types/layout";

const DEFAULT_SLIDE_WIDTH = 1280;
const DEFAULT_SLIDE_HEIGHT = 720;
const DEFAULT_FONT: Font = {
  family: "Arial",
  size: 16,
  color: "111111",
};

type RenderMode = "absolute" | "flow";

interface FrameElement {
  position?: { x: number; y: number } | null;
  size?: { width: number; height: number } | null;
  rotation?: number | null;
}

export interface SlideLayoutRendererProps {
  layout: SlideLayout;
  width?: number;
  height?: number;
  showComponentBounds?: boolean;
  showMissingImageMarkers?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function SlideLayoutRenderer({
  layout,
  width = DEFAULT_SLIDE_WIDTH,
  height = DEFAULT_SLIDE_HEIGHT,
  showComponentBounds = false,
  showMissingImageMarkers = true,
  className,
  style,
}: SlideLayoutRendererProps) {
  const renderOptions = { showMissingImageMarkers };

  return (
    <section
      aria-label={layout.description || layout.id}
      className={className}
      style={{
        position: "relative",
        boxSizing: "border-box",
        width,
        height,
        overflow: "hidden",
        background: "white",
        ...style,
      }}
    >
      {layout.components.map((component, componentIndex) =>
        renderComponent(
          component,
          `${component.id}-${componentIndex}`,
          showComponentBounds,
          renderOptions,
        ),
      )}
    </section>
  );
}

interface RenderOptions {
  showMissingImageMarkers: boolean;
}

function renderComponent(
  component: SlideComponent,
  key: string,
  showComponentBounds: boolean,
  options: RenderOptions,
) {
  return (
    <div
      key={key}
      style={{
        ...frameStyle(component, "absolute"),
        overflow: "visible",
      }}
    >
      {component.elements.map((element, elementIndex) =>
        renderElement(
          element,
          `${key}-element-${elementIndex}`,
          "absolute",
          options,
        ),
      )}
      {showComponentBounds ? renderComponentBounds(component.id) : null}
    </div>
  );
}

function renderComponentBounds(componentId: string) {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: -10,
        zIndex: 9999,
        pointerEvents: "none",
        border: "2px solid rgba(34, 197, 94, 0.95)",
        boxSizing: "border-box",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: -2,
          right: -2,
          maxWidth: "100%",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          background: "rgba(22, 163, 74, 0.95)",
          color: "white",
          font: "12px Arial, sans-serif",
          lineHeight: "18px",
          padding: "0 6px",
        }}
      >
        {componentId}
      </span>
    </div>
  );
}

function renderElement(
  element: SlideElement,
  key: string,
  mode: RenderMode,
  options: RenderOptions,
): ReactNode {
  switch (element.type) {
    case "text":
      return renderTextElement(element, key, mode);
    case "rich-text":
      return renderRichTextElement(element, key, mode);
    case "container":
      return (
        <div
          key={key}
          style={{
            ...frameStyle(element, mode),
            ...fillStyle(element.fill),
            ...borderStyle(element.stroke),
            ...borderRadiusStyle(element.borderRadius),
            ...boxShadowStyle(element.shadow),
            ...paddingStyle(element.padding),
          }}
        >
          {element.child
            ? renderElement(element.child, `${key}-child`, "absolute", options)
            : null}
        </div>
      );
    case "image":
      return renderImageElement(element, key, mode, options);
    case "list":
      return renderListElement(element, key, mode);
    case "table":
      return renderTableElement(element, key, mode);
    case "rectangle":
      return (
        <div
          key={key}
          style={{
            ...frameStyle(element, mode),
            ...fillStyle(element.fill),
            ...borderStyle(element.stroke),
            ...borderRadiusStyle(element.borderRadius),
            ...boxShadowStyle(element.shadow),
          }}
        />
      );
    case "ellipse":
      return (
        <div
          key={key}
          style={{
            ...frameStyle(element, mode),
            ...fillStyle(element.fill),
            ...borderStyle(element.stroke),
            ...boxShadowStyle(element.shadow),
            borderRadius: "50%",
          }}
        />
      );
    case "line":
      return renderLineElement(element, key, mode);
    case "chart":
      return renderChartElement(element, key, mode);
    case "flex":
      return (
        <div
          key={key}
          style={{
            ...frameStyle(element, mode),
            display: "flex",
            flexDirection: element.direction,
            flexWrap: element.wrap ? "wrap" : "nowrap",
            alignItems: element.alignItems ?? undefined,
            justifyContent: element.justifyContent ?? undefined,
            gap: element.gap ?? undefined,
            columnGap: element.columnGap ?? undefined,
            rowGap: element.rowGap ?? undefined,
          }}
        >
          {element.children.map((child, index) =>
            renderElement(child, `${key}-child-${index}`, "flow", options),
          )}
        </div>
      );
    case "grid":
      return (
        <div
          key={key}
          style={{
            ...frameStyle(element, mode),
            display: "grid",
            gridTemplateColumns: `repeat(${element.columns}, minmax(0, 1fr))`,
            gridTemplateRows: element.rows
              ? `repeat(${element.rows}, minmax(0, 1fr))`
              : undefined,
            alignItems: element.alignItems ?? undefined,
            justifyItems: element.justifyItems ?? undefined,
            gap: element.gap ?? undefined,
            columnGap: element.columnGap ?? undefined,
            rowGap: element.rowGap ?? undefined,
          }}
        >
          {element.children.map((child, index) =>
            renderElement(child, `${key}-child-${index}`, "flow", options),
          )}
        </div>
      );
    case "stack":
      return (
        <div
          key={key}
          style={{
            ...frameStyle(element, mode),
          }}
        >
          {element.children.map((child, index) =>
            renderElement(child, `${key}-child-${index}`, "absolute", options),
          )}
        </div>
      );
  }
}

function renderTextElement(
  element: Extract<SlideElement, { type: "text" }>,
  key: string,
  mode: RenderMode,
) {
  return (
    <div
      key={key}
      style={{
        ...textFrameStyle(element, mode, element.font, element.alignment),
        ...fillStyle(element.fill),
        ...textStrokeStyle(element.stroke),
        ...textShadowStyle(element.shadow),
      }}
    >
      {element.text ?? ""}
    </div>
  );
}

function renderRichTextElement(
  element: Extract<SlideElement, { type: "rich-text" }>,
  key: string,
  mode: RenderMode,
) {
  const baseFont = element.font ?? DEFAULT_FONT;

  return (
    <div
      key={key}
      style={{
        ...textFrameStyle(element, mode, baseFont, element.alignment),
        ...fillStyle(element.fill),
        ...textStrokeStyle(element.stroke),
        ...textShadowStyle(element.shadow),
      }}
    >
      {renderRichTextRuns(element.runs, baseFont)}
    </div>
  );
}

function renderImageElement(
  element: ImageElement,
  key: string,
  mode: RenderMode,
  options: RenderOptions,
) {
  const src = imageSource(element.data);
  const style = frameStyle(element, mode);

  if (!src) {
    if (!options.showMissingImageMarkers) {
      return <div key={key} style={style} />;
    }

    return (
      <div
        key={key}
        style={{
          ...style,
          display: "grid",
          placeItems: "center",
          border: "2px solid #94a3b8",
          color: "#475569",
          font: "12px Arial, sans-serif",
          background: "rgba(241, 245, 249, 0.75)",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 4,
            right: 6,
            maxWidth: "calc(100% - 12px)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          Missing image: {element.name ?? "Image"}
        </span>
      </div>
    );
  }

  return (
    <img
      key={key}
      src={src}
      alt={element.name ?? ""}
      style={{
        ...style,
        objectFit: element.fit ?? "contain",
      }}
    />
  );
}

function renderListElement(
  element: Extract<SlideElement, { type: "list" }>,
  key: string,
  mode: RenderMode,
) {
  const Tag = element.marker === "number" ? "ol" : "ul";
  const font = element.font ?? DEFAULT_FONT;

  return (
    <Tag
      key={key}
      style={{
        ...frameStyle(element, mode),
        ...fontStyle(font),
        listStyleType:
          element.marker === "none"
            ? "none"
            : element.marker === "number"
              ? "decimal"
              : "disc",
        margin: 0,
        paddingLeft: element.marker === "none" ? 0 : font.size * 1.4,
      }}
    >
      {(element.items ?? []).map((item, index) => (
        <li key={`${key}-item-${index}`}>{renderListItem(item, font)}</li>
      ))}
    </Tag>
  );
}

function renderTableElement(
  element: Extract<SlideElement, { type: "table" }>,
  key: string,
  mode: RenderMode,
) {
  const rows = [element.columns, ...element.rows];
  const columnCount = Math.max(...rows.map((row) => row.length), 1);

  return (
    <div
      key={key}
      style={{
        ...frameStyle(element, mode),
        display: "grid",
        gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))`,
        overflow: "hidden",
      }}
    >
      {rows.flatMap((row, rowIndex) =>
        row.map((cell, cellIndex) => (
          <div
            key={`${key}-cell-${rowIndex}-${cellIndex}`}
            style={{
              minHeight: 32,
              padding: 8,
              display: "flex",
              alignItems: "center",
              ...fillStyle(cell.fill),
              ...borderStyle(cell.stroke ?? { color: "dddddd", width: 1 }),
            }}
          >
            {cell.text ?? ""}
          </div>
        )),
      )}
    </div>
  );
}

function renderLineElement(
  element: Extract<SlideElement, { type: "line" }>,
  key: string,
  mode: RenderMode,
) {
  const width = Math.max(element.size?.width ?? 1, 1);
  const height = Math.max(element.size?.height ?? element.stroke.width, element.stroke.width);
  const color = cssColor(element.stroke.color) ?? "black";

  return (
    <svg
      key={key}
      viewBox={`0 0 ${width} ${height}`}
      style={{
        ...frameStyle({ ...element, size: { width, height } }, mode),
        overflow: "visible",
        ...boxShadowStyle(element.shadow),
      }}
    >
      <line
        x1="0"
        y1={height / 2}
        x2={width}
        y2={height / 2}
        stroke={color}
        strokeOpacity={element.stroke.opacity ?? undefined}
        strokeWidth={element.stroke.width}
        strokeDasharray={element.stroke.dash?.join(" ") || undefined}
      />
    </svg>
  );
}

function renderChartElement(
  element: ChartElement,
  key: string,
  mode: RenderMode,
) {
  const titleHeight = element.title ? 26 : 0;

  return (
    <div
      key={key}
      style={{
        ...frameStyle(element, mode),
        color: cssColor(element.labelColor) ?? "#222222",
        font: "12px Arial, sans-serif",
      }}
    >
      {element.title ? (
        <div style={{ height: titleHeight, fontWeight: 700 }}>{element.title}</div>
      ) : null}
      <div
        style={{
          position: "absolute",
          inset: `${titleHeight}px 0 0 0`,
        }}
      >
        {element.chartType === "donut"
          ? renderDonutChart(element)
          : renderCartesianChart(element)}
      </div>
    </div>
  );
}

function renderCartesianChart(element: ChartElement) {
  const data = element.data;
  const maxValue = Math.max(...data.map((datum) => datum.value), 1);
  const axisColor = cssColor(element.axisColor) ?? "#999999";
  const fallbackColor = cssColor(element.color) ?? "#3b82f6";
  const points = data
    .map((datum, index) => {
      const x = data.length <= 1 ? 50 : 10 + (index / (data.length - 1)) * 80;
      const y = 90 - (datum.value / maxValue) * 80;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
      <line x1="8" y1="90" x2="96" y2="90" stroke={axisColor} strokeWidth="0.8" />
      <line x1="8" y1="8" x2="8" y2="90" stroke={axisColor} strokeWidth="0.8" />
      {element.chartType === "line" ? (
        <polyline points={points} fill="none" stroke={fallbackColor} strokeWidth="2" />
      ) : (
        data.map((datum, index) => {
          const slotWidth = 80 / Math.max(data.length, 1);
          const barWidth = slotWidth * 0.6;
          const height = (datum.value / maxValue) * 80;
          return (
            <rect
              key={`${datum.label}-${index}`}
              x={12 + index * slotWidth}
              y={90 - height}
              width={barWidth}
              height={height}
              fill={cssColor(datum.color) ?? fallbackColor}
            />
          );
        })
      )}
    </svg>
  );
}

function renderDonutChart(element: ChartElement) {
  const total = element.data.reduce((sum, datum) => sum + Math.max(datum.value, 0), 0);
  const fallbackColor = cssColor(element.color) ?? "#3b82f6";
  let cursor = 0;
  const gradient = element.data
    .map((datum) => {
      const start = total > 0 ? (cursor / total) * 360 : 0;
      cursor += Math.max(datum.value, 0);
      const end = total > 0 ? (cursor / total) * 360 : 360;
      return `${cssColor(datum.color) ?? fallbackColor} ${start}deg ${end}deg`;
    })
    .join(", ");

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        borderRadius: "50%",
        background: gradient ? `conic-gradient(${gradient})` : fallbackColor,
        position: "relative",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: "28%",
          borderRadius: "50%",
          background: "white",
        }}
      />
    </div>
  );
}

function renderListItem(item: ListItem, baseFont: Font) {
  if (item.type === "text") {
    return item.text;
  }

  return renderRichTextRuns(item.runs, baseFont);
}

function renderRichTextRuns(
  runs: RichTextRun[] | null | undefined,
  baseFont: Font,
) {
  return (runs ?? []).map((run, index) => (
    <span key={`${run.text}-${index}`} style={fontStyle(run.font ?? baseFont)}>
      {run.text}
    </span>
  ));
}

function frameStyle(element: FrameElement, mode: RenderMode): CSSProperties {
  const style: CSSProperties = {
    boxSizing: "border-box",
  };

  if (mode === "absolute") {
    style.position = "absolute";
    style.left = element.position?.x ?? 0;
    style.top = element.position?.y ?? 0;
  } else {
    style.position = "relative";
    style.flex = element.size ? "0 0 auto" : undefined;
  }

  if (element.size) {
    style.width = element.size.width;
    style.height = element.size.height;
  }

  if (element.rotation) {
    style.transform = `rotate(${element.rotation}deg)`;
    style.transformOrigin = "top left";
  }

  return style;
}

function textFrameStyle(
  element: FrameElement,
  mode: RenderMode,
  font: Font,
  alignment?: Alignment | null,
): CSSProperties {
  const wrap = font.wrap ?? "word";
  const style: CSSProperties = {
    ...frameStyle(element, mode),
    ...fontStyle(font),
    display: "flex",
    flexDirection: "column",
    justifyContent: verticalAlignment(alignment),
    alignItems: horizontalAlignment(alignment),
    textAlign: alignment?.horizontal ?? "left",
    overflow: font.ellipsis ? "hidden" : undefined,
    textOverflow: font.ellipsis ? "ellipsis" : undefined,
    whiteSpace: wrap === "none" ? "nowrap" : "pre-wrap",
    overflowWrap: wrap === "char" ? "anywhere" : "break-word",
  };

  return style;
}

function fontStyle(font: Font): CSSProperties {
  return {
    fontFamily: font.family,
    fontSize: font.size,
    color: cssColor(font.color) ?? undefined,
    fontWeight: font.bold ? 700 : 400,
    fontStyle: font.italic ? "italic" : "normal",
    lineHeight: font.lineHeight ? `${font.lineHeight}px` : undefined,
    letterSpacing:
      font.letterSpacing != null ? `${font.letterSpacing}px` : undefined,
  };
}

function fillStyle(fill?: Fill | null): CSSProperties {
  return {
    backgroundColor: cssColor(fill?.color),
    opacity: fill?.opacity ?? undefined,
  };
}

function borderStyle(stroke?: Stroke | null): CSSProperties {
  if (!stroke) {
    return {};
  }

  return {
    border: `${stroke.width}px ${stroke.dash?.length ? "dashed" : "solid"} ${
      cssColor(stroke.color) ?? "black"
    }`,
  };
}

function textStrokeStyle(stroke?: Stroke | null): CSSProperties {
  if (!stroke) {
    return {};
  }

  return {
    WebkitTextStroke: `${stroke.width}px ${cssColor(stroke.color) ?? "black"}`,
  };
}

function borderRadiusStyle(radius?: BorderRadius | null): CSSProperties {
  if (!radius) {
    return {};
  }

  return {
    borderRadius: `${radius.tl}px ${radius.tr}px ${radius.br}px ${radius.bl}px`,
  };
}

function boxShadowStyle(shadow?: Shadow | null): CSSProperties {
  const shadowValue = shadowCss(shadow);

  return shadowValue ? { boxShadow: shadowValue } : {};
}

function textShadowStyle(shadow?: Shadow | null): CSSProperties {
  const shadowValue = shadowCss(shadow);

  return shadowValue ? { textShadow: shadowValue } : {};
}

function shadowCss(shadow?: Shadow | null) {
  if (!shadow) {
    return undefined;
  }

  const color = cssColor(shadow.color) ?? "rgba(0, 0, 0, 0.25)";

  return `${shadow.offsetX ?? 0}px ${shadow.offsetY ?? 0}px ${
    shadow.blur ?? 0
  }px ${color}`;
}

function paddingStyle(padding?: Padding | null): CSSProperties {
  if (!padding) {
    return {};
  }

  return {
    paddingTop: padding.top,
    paddingRight: padding.right,
    paddingBottom: padding.bottom,
    paddingLeft: padding.left,
  };
}

function horizontalAlignment(alignment?: Alignment | null) {
  switch (alignment?.horizontal) {
    case "center":
      return "center";
    case "right":
      return "flex-end";
    case "left":
    default:
      return "flex-start";
  }
}

function verticalAlignment(alignment?: Alignment | null) {
  switch (alignment?.vertical) {
    case "middle":
      return "center";
    case "bottom":
      return "flex-end";
    case "top":
    default:
      return "flex-start";
  }
}

function imageSource(data?: string | null) {
  if (!data || data === "icon_placeholder" || data === "image_placeholder") {
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

function cssColor(color?: string | null) {
  if (!color) {
    return undefined;
  }

  if (/^[0-9a-fA-F]{3,8}$/.test(color)) {
    return `#${color}`;
  }

  return color;
}
