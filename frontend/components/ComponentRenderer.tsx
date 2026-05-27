"use client";

import ElementRenderer from "@/components/ElementRenderer";
import { forwardRef, useEffect, useRef, useState } from "react";
import { Group, Rect, Text, Transformer } from "react-konva";
import type Konva from "konva";
import type { SlideComponent } from "@/types/component";
import type {
  BorderRadius,
  Font,
  Padding,
  Position,
  Shadow,
  Size,
  SlideElement,
  Stroke,
  TextElement,
} from "@/types/elements";

const MIN_COMPONENT_WIDTH = 80;
const MIN_COMPONENT_HEIGHT = 60;
const MIN_ELEMENT_WIDTH = 8;
const MIN_ELEMENT_HEIGHT = 8;
const DEFAULT_TEXT_FONT_FAMILY = "Arial";
const DEFAULT_TEXT_FONT_SIZE = 16;
const TEXT_EDITOR_HEIGHT = 34;
const TEXT_EDITOR_WIDTH = 336;
const TEXT_EDITOR_GAP = 8;
const TEXT_EDITOR_FONT_FAMILIES = [
  "Arial",
  "Helvetica",
  "Georgia",
  "Times New Roman",
  "Courier New",
];
const MIN_TEXT_EDITOR_FONT_SIZE = 6;
const MAX_TEXT_EDITOR_FONT_SIZE = 96;

interface Frame {
  x: number;
  y: number;
  width: number;
  height: number;
}

type ElementPathSegment =
  | { kind: "root"; index: number }
  | { kind: "child" }
  | { kind: "children"; index: number }
  | { kind: "item" };

type SelectedElementLayoutMode = "absolute" | "layout-flow" | "repeated-flow";

interface SelectedElement {
  element: SlideElement;
  frame: Frame;
  parentFrame: Frame;
  path: ElementPathSegment[];
  layoutMode: SelectedElementLayoutMode;
}

interface SelectedTextElement extends Omit<SelectedElement, "element"> {
  element: TextElement;
}

interface DraftComponent {
  source: SlideComponent;
  component: SlideComponent;
}

export type ComponentRendererProps =
  | ({
      component: SlideComponent;
      isSelected?: boolean;
      isElementSelectionActive?: boolean;
      showBounds?: boolean;
      showMissingImageMarkers?: boolean;
      onSelect?: () => void;
      onElementSelect?: () => void;
      onComponentChange?: (component: SlideComponent) => void;
    })
  | (SlideComponent & {
      isSelected?: boolean;
      isElementSelectionActive?: boolean;
      showBounds?: boolean;
      showMissingImageMarkers?: boolean;
      onSelect?: () => void;
      onElementSelect?: () => void;
      onComponentChange?: (component: SlideComponent) => void;
    });

export default function ComponentRenderer(props: ComponentRendererProps) {
  const {
    component,
    isSelected = false,
    isElementSelectionActive = false,
    showBounds = false,
    showMissingImageMarkers = true,
    onSelect,
    onElementSelect,
    onComponentChange,
  } = normalizeComponentRendererProps(props);
  const groupRef = useRef<Konva.Group>(null);
  const contentRef = useRef<Konva.Group>(null);
  const frameRef = useRef<Konva.Rect>(null);
  const transformerRef = useRef<Konva.Transformer>(null);
  const elementFrameRef = useRef<Konva.Rect>(null);
  const elementTransformerRef = useRef<Konva.Transformer>(null);
  const [draftComponent, setDraftComponent] = useState<DraftComponent | null>(null);
  const [selectedElement, setSelectedElement] = useState<SelectedElement | null>(
    null,
  );
  const editableComponent =
    draftComponent?.source === component ? draftComponent.component : component;
  const componentWidth = editableComponent.size?.width ?? 0;
  const componentHeight = editableComponent.size?.height ?? 0;
  const selectedTextSelection: SelectedTextElement | null =
    isElementSelectionActive && selectedElement?.element.type === "text"
      ? { ...selectedElement, element: selectedElement.element }
      : null;

  useEffect(() => {
    if (!isSelected || !frameRef.current || !transformerRef.current) {
      return;
    }

    transformerRef.current.nodes([frameRef.current]);
    transformerRef.current.forceUpdate();
    transformerRef.current.getLayer()?.batchDraw();
  }, [componentHeight, componentWidth, isSelected]);

  useEffect(() => {
    if (
      !isElementSelectionActive ||
      !selectedElement ||
      !elementFrameRef.current ||
      !elementTransformerRef.current
    ) {
      return;
    }

    elementTransformerRef.current.nodes([elementFrameRef.current]);
    elementTransformerRef.current.forceUpdate();
    elementTransformerRef.current.getLayer()?.batchDraw();
  }, [
    isElementSelectionActive,
    selectedElement,
    selectedElement?.frame.height,
    selectedElement?.frame.width,
    selectedElement?.frame.x,
    selectedElement?.frame.y,
  ]);

  const previewFrameTransform = () => {
    const contentNode = contentRef.current;
    const frameNode = frameRef.current;

    if (!contentNode || !frameNode) {
      return;
    }

    contentNode.x(frameNode.x());
    contentNode.y(frameNode.y());
    contentNode.scaleX(frameNode.scaleX());
    contentNode.scaleY(frameNode.scaleY());
    contentNode.getLayer()?.batchDraw();
  };

  const commitFrameTransform = () => {
    const groupNode = groupRef.current;
    const contentNode = contentRef.current;
    const frameNode = frameRef.current;

    if (!groupNode || !contentNode || !frameNode) {
      return;
    }

    const scaleX = frameNode.scaleX();
    const scaleY = frameNode.scaleY();
    const nextWidth = Math.max(componentWidth * scaleX, MIN_COMPONENT_WIDTH);
    const nextHeight = Math.max(componentHeight * scaleY, MIN_COMPONENT_HEIGHT);
    const normalizedScaleX = componentWidth > 0 ? nextWidth / componentWidth : 1;
    const normalizedScaleY = componentHeight > 0 ? nextHeight / componentHeight : 1;
    const nextPosition = {
      x: groupNode.x() + frameNode.x(),
      y: groupNode.y() + frameNode.y(),
    };

    frameNode.x(0);
    frameNode.y(0);
    frameNode.scaleX(1);
    frameNode.scaleY(1);
    contentNode.x(0);
    contentNode.y(0);
    contentNode.scaleX(1);
    contentNode.scaleY(1);
    groupNode.x(nextPosition.x);
    groupNode.y(nextPosition.y);
    setSelectedElement(null);
    onComponentChange?.({
      ...editableComponent,
      position: nextPosition,
      size: {
        width: nextWidth,
        height: nextHeight,
      },
      elements: editableComponent.elements.map((element) =>
        scaleElement(element, normalizedScaleX, normalizedScaleY),
      ),
    });
  };

  const previewSelectedElementFrame = () => {
    const nextFrame = selectedElementFrameFromNode(elementFrameRef.current);

    if (!nextFrame) {
      return;
    }

    normalizeSelectedElementFrameNode(elementFrameRef.current, nextFrame);
    applySelectedElementFrame(nextFrame, false);
  };

  const commitSelectedElementFrame = () => {
    const nextFrame = selectedElementFrameFromNode(elementFrameRef.current);

    if (!nextFrame) {
      return;
    }

    normalizeSelectedElementFrameNode(elementFrameRef.current, nextFrame);
    applySelectedElementFrame(nextFrame, true);
  };

  const applySelectedElementFrame = (nextFrame: Frame, shouldCommit: boolean) => {
    if (!selectedElement) {
      return;
    }

    let nextSelectedElement: SelectedElement | null = null;
    const nextElements = updateElementAtPath(
      component.elements,
      selectedElement.path,
      (element) => {
        const nextElement = elementWithFrame(
          element,
          nextFrame,
          selectedElement.parentFrame,
          selectedElement.layoutMode,
        );

        nextSelectedElement = {
          ...selectedElement,
          element: nextElement,
          frame: nextFrame,
        };

        return nextElement;
      },
    );
    const nextComponent = {
      ...component,
      elements: nextElements,
    };

    setDraftComponent({
      source: component,
      component: nextComponent,
    });

    if (nextSelectedElement) {
      setSelectedElement(nextSelectedElement);
    }

    if (shouldCommit) {
      onComponentChange?.(nextComponent);
    }
  };

  const applySelectedTextFont = (updater: (font: Font) => Font) => {
    if (!selectedTextSelection) {
      return;
    }

    let nextSelectedElement: SelectedElement | null = null;
    const nextElements = updateElementAtPath(
      editableComponent.elements,
      selectedTextSelection.path,
      (element) => {
        if (element.type !== "text") {
          return element;
        }

        const nextElement = {
          ...element,
          font: updater(element.font ?? {}),
        };

        nextSelectedElement = {
          ...selectedTextSelection,
          element: nextElement,
        };

        return nextElement;
      },
    );
    const nextComponent = {
      ...editableComponent,
      elements: nextElements,
    };

    setDraftComponent({
      source: component,
      component: nextComponent,
    });

    if (nextSelectedElement) {
      setSelectedElement(nextSelectedElement);
    }

    onComponentChange?.(nextComponent);
  };

  return (
    <>
      <Group
        ref={groupRef}
        x={editableComponent.position?.x ?? 0}
        y={editableComponent.position?.y ?? 0}
        draggable={!isElementSelectionActive}
        onMouseDown={(event) => {
          event.cancelBubble = true;

          if (!isElementSelectionActive) {
            setSelectedElement(null);
            onSelect?.();
          }
        }}
        onTouchStart={(event) => {
          event.cancelBubble = true;

          if (!isElementSelectionActive) {
            setSelectedElement(null);
            onSelect?.();
          }
        }}
        onDblClick={(event) => {
          event.cancelBubble = true;

          if (!isSelected && !isElementSelectionActive) {
            return;
          }

          const pointer = event.target.getStage()?.getPointerPosition();
          const groupNode = groupRef.current;

          if (!pointer || !groupNode) {
            return;
          }

          const transform = groupNode.getAbsoluteTransform().copy();
          transform.invert();
          const localPoint = transform.point(pointer);
          const nextSelection = nextElementSelection(
            editableComponent.elements,
            localPoint,
            isElementSelectionActive ? selectedElement : null,
            {
              x: 0,
              y: 0,
              width: componentWidth,
              height: componentHeight,
            },
          );

          if (nextSelection) {
            setSelectedElement(nextSelection);
            onElementSelect?.();
          }
        }}
        onDblTap={(event) => {
          event.cancelBubble = true;

          if (!isSelected && !isElementSelectionActive) {
            return;
          }

          const pointer = event.target.getStage()?.getPointerPosition();
          const groupNode = groupRef.current;

          if (!pointer || !groupNode) {
            return;
          }

          const transform = groupNode.getAbsoluteTransform().copy();
          transform.invert();
          const localPoint = transform.point(pointer);
          const nextSelection = nextElementSelection(
            editableComponent.elements,
            localPoint,
            isElementSelectionActive ? selectedElement : null,
            {
              x: 0,
              y: 0,
              width: componentWidth,
              height: componentHeight,
            },
          );

          if (nextSelection) {
            setSelectedElement(nextSelection);
            onElementSelect?.();
          }
        }}
        onDragEnd={(event) => {
          if (event.target !== groupRef.current) {
            return;
          }

          onComponentChange?.({
            ...editableComponent,
            position: {
              x: event.target.x(),
              y: event.target.y(),
            },
          });
        }}
      >
        <Group ref={contentRef}>
          <Rect
            width={componentWidth}
            height={componentHeight}
            fill="rgba(255,255,255,0.001)"
          />
          {editableComponent.elements.map((element, index) => (
            <ElementRenderer
              key={`${editableComponent.id}-element-${index}`}
              element={element}
              mode="absolute"
              showMissingImageMarkers={showMissingImageMarkers}
            />
          ))}
          {isElementSelectionActive && selectedElement ? (
            <SelectedElementFrame
              ref={elementFrameRef}
              frame={selectedElement.frame}
              onMouseDown={(event) => {
                event.cancelBubble = true;
              }}
              onTouchStart={(event) => {
                event.cancelBubble = true;
              }}
              onDragMove={(event) => {
                event.cancelBubble = true;
                previewSelectedElementFrame();
              }}
              onDragEnd={(event) => {
                event.cancelBubble = true;
                commitSelectedElementFrame();
              }}
              onTransform={(event) => {
                event.cancelBubble = true;
                previewSelectedElementFrame();
              }}
              onTransformEnd={(event) => {
                event.cancelBubble = true;
                commitSelectedElementFrame();
              }}
            />
          ) : null}
          {selectedTextSelection ? (
            <TextEditorBar
              frame={selectedTextSelection.frame}
              element={selectedTextSelection.element}
              containerWidth={componentWidth}
              onToggleBold={() => {
                applySelectedTextFont((font) => ({
                  ...font,
                  bold: !(font.bold ?? false),
                }));
              }}
              onToggleItalic={() => {
                applySelectedTextFont((font) => ({
                  ...font,
                  italic: !(font.italic ?? false),
                }));
              }}
              onDecreaseFontSize={() => {
                applySelectedTextFont((font) =>
                  textFontWithSize(
                    font,
                    Math.max(
                      Math.round((font.size ?? DEFAULT_TEXT_FONT_SIZE) - 1),
                      MIN_TEXT_EDITOR_FONT_SIZE,
                    ),
                  ),
                );
              }}
              onIncreaseFontSize={() => {
                applySelectedTextFont((font) =>
                  textFontWithSize(
                    font,
                    Math.min(
                      Math.round((font.size ?? DEFAULT_TEXT_FONT_SIZE) + 1),
                      MAX_TEXT_EDITOR_FONT_SIZE,
                    ),
                  ),
                );
              }}
              onCycleFontFamily={() => {
                applySelectedTextFont((font) => ({
                  ...font,
                  family: nextTextEditorFontFamily(font.family),
                }));
              }}
            />
          ) : null}
          {showBounds ? (
            <ComponentBounds
              componentId={editableComponent.id}
              width={componentWidth}
              height={componentHeight}
            />
          ) : null}
        </Group>
        {isSelected ? (
          <SelectedComponentFrame
            ref={frameRef}
            width={componentWidth}
            height={componentHeight}
          />
        ) : null}
      </Group>
      {isSelected ? (
        <Transformer
          ref={transformerRef}
          rotateEnabled={false}
          flipEnabled={false}
          keepRatio={false}
          ignoreStroke
          padding={0}
          borderStroke="#2563EB"
          borderStrokeWidth={2}
          anchorFill="#FFFFFF"
          anchorStroke="#2563EB"
          anchorStrokeWidth={2}
          anchorSize={9}
          enabledAnchors={[
            "top-left",
            "top-center",
            "top-right",
            "middle-right",
            "bottom-right",
            "bottom-center",
            "bottom-left",
            "middle-left",
          ]}
          boundBoxFunc={(oldBox, newBox) => {
            if (
              Math.abs(newBox.width) < MIN_COMPONENT_WIDTH ||
              Math.abs(newBox.height) < MIN_COMPONENT_HEIGHT
            ) {
              return oldBox;
            }

            return newBox;
          }}
          onTransform={previewFrameTransform}
          onTransformEnd={commitFrameTransform}
        />
      ) : null}
      {isElementSelectionActive && selectedElement ? (
        <Transformer
          ref={elementTransformerRef}
          rotateEnabled={false}
          flipEnabled={false}
          keepRatio={false}
          ignoreStroke
          padding={0}
          borderStroke="#F59E0B"
          borderStrokeWidth={2}
          anchorFill="#FFFFFF"
          anchorStroke="#F59E0B"
          anchorStrokeWidth={2}
          anchorSize={8}
          enabledAnchors={[
            "top-left",
            "top-center",
            "top-right",
            "middle-right",
            "bottom-right",
            "bottom-center",
            "bottom-left",
            "middle-left",
          ]}
          boundBoxFunc={(oldBox, newBox) => {
            if (
              Math.abs(newBox.width) < MIN_ELEMENT_WIDTH ||
              Math.abs(newBox.height) < MIN_ELEMENT_HEIGHT
            ) {
              return oldBox;
            }

            return newBox;
          }}
        />
      ) : null}
    </>
  );
}

export { ComponentRenderer };

const SelectedComponentFrame = forwardRef<
  Konva.Rect,
  {
    width: number;
    height: number;
  }
>(function SelectedComponentFrame({ width, height }, ref) {
  return (
    <Rect
      ref={ref}
      listening={false}
      width={width}
      height={height}
      stroke="#2563EB"
      strokeWidth={2}
      dash={[8, 6]}
    />
  );
});

const SelectedElementFrame = forwardRef<
  Konva.Rect,
  {
    frame: Frame;
    onMouseDown: (event: Konva.KonvaEventObject<MouseEvent>) => void;
    onTouchStart: (event: Konva.KonvaEventObject<TouchEvent>) => void;
    onDragMove: (event: Konva.KonvaEventObject<DragEvent>) => void;
    onDragEnd: (event: Konva.KonvaEventObject<DragEvent>) => void;
    onTransform: (event: Konva.KonvaEventObject<Event>) => void;
    onTransformEnd: (event: Konva.KonvaEventObject<Event>) => void;
  }
>(function SelectedElementFrame(
  {
    frame,
    onMouseDown,
    onTouchStart,
    onDragMove,
    onDragEnd,
    onTransform,
    onTransformEnd,
  },
  ref,
) {
  return (
    <Rect
      ref={ref}
      x={frame.x}
      y={frame.y}
      width={frame.width}
      height={frame.height}
      draggable
      fill="rgba(245, 158, 11, 0.001)"
      stroke="#F59E0B"
      strokeWidth={2}
      dash={[4, 4]}
      onMouseDown={onMouseDown}
      onTouchStart={onTouchStart}
      onDragMove={onDragMove}
      onDragEnd={onDragEnd}
      onTransform={onTransform}
      onTransformEnd={onTransformEnd}
    />
  );
});

function TextEditorBar({
  frame,
  element,
  containerWidth,
  onToggleBold,
  onToggleItalic,
  onDecreaseFontSize,
  onIncreaseFontSize,
  onCycleFontFamily,
}: {
  frame: Frame;
  element: TextElement;
  containerWidth: number;
  onToggleBold: () => void;
  onToggleItalic: () => void;
  onDecreaseFontSize: () => void;
  onIncreaseFontSize: () => void;
  onCycleFontFamily: () => void;
}) {
  const font = element.font ?? {};
  const fontSize = Math.round(font.size ?? DEFAULT_TEXT_FONT_SIZE);
  const family = font.family ?? DEFAULT_TEXT_FONT_FAMILY;
  const x = Math.max(
    0,
    Math.min(frame.x, Math.max(containerWidth - TEXT_EDITOR_WIDTH, 0)),
  );
  const y =
    frame.y >= TEXT_EDITOR_HEIGHT + TEXT_EDITOR_GAP
      ? frame.y - TEXT_EDITOR_HEIGHT - TEXT_EDITOR_GAP
      : frame.y + frame.height + TEXT_EDITOR_GAP;

  return (
    <Group
      x={x}
      y={y}
      onMouseDown={cancelTextEditorEvent}
      onTouchStart={cancelTextEditorEvent}
      onClick={cancelTextEditorEvent}
      onTap={cancelTextEditorEvent}
    >
      <Rect
        width={TEXT_EDITOR_WIDTH}
        height={TEXT_EDITOR_HEIGHT}
        fill="#FFFFFF"
        stroke="#CBD5E1"
        strokeWidth={1}
        cornerRadius={6}
        shadowColor="#0F172A"
        shadowBlur={10}
        shadowOpacity={0.14}
        shadowOffsetY={4}
      />
      <TextEditorButton
        x={6}
        label="B"
        width={30}
        active={font.bold ?? false}
        fontStyle="bold"
        onPress={onToggleBold}
      />
      <TextEditorButton
        x={40}
        label="I"
        width={30}
        active={font.italic ?? false}
        fontStyle="italic"
        onPress={onToggleItalic}
      />
      <TextEditorButton
        x={80}
        label="-"
        width={28}
        onPress={onDecreaseFontSize}
      />
      <Text
        x={110}
        y={7}
        width={44}
        height={20}
        text={`${fontSize}px`}
        align="center"
        verticalAlign="middle"
        fontFamily="Arial"
        fontSize={12}
        fill="#0F172A"
      />
      <TextEditorButton
        x={156}
        label="+"
        width={28}
        onPress={onIncreaseFontSize}
      />
      <TextEditorButton
        x={194}
        label={family}
        width={136}
        fontFamily={family}
        onPress={onCycleFontFamily}
      />
    </Group>
  );
}

function TextEditorButton({
  x,
  label,
  width,
  active = false,
  fontFamily = "Arial",
  fontStyle = "normal",
  onPress,
}: {
  x: number;
  label: string;
  width: number;
  active?: boolean;
  fontFamily?: string;
  fontStyle?: string;
  onPress: () => void;
}) {
  return (
    <Group
      x={x}
      y={5}
      onMouseDown={cancelTextEditorEvent}
      onTouchStart={cancelTextEditorEvent}
      onClick={(event) => {
        event.cancelBubble = true;
        onPress();
      }}
      onTap={(event) => {
        event.cancelBubble = true;
        onPress();
      }}
    >
      <Rect
        width={width}
        height={24}
        fill={active ? "#2563EB" : "#F8FAFC"}
        stroke={active ? "#2563EB" : "#E2E8F0"}
        strokeWidth={1}
        cornerRadius={5}
      />
      <Text
        width={width}
        height={24}
        text={label}
        align="center"
        verticalAlign="middle"
        fontFamily={fontFamily}
        fontSize={12}
        fontStyle={fontStyle}
        fill={active ? "#FFFFFF" : "#0F172A"}
        wrap="none"
        ellipsis
      />
    </Group>
  );
}

function cancelTextEditorEvent(
  event: Konva.KonvaEventObject<MouseEvent | TouchEvent>,
) {
  event.cancelBubble = true;
}

function textFontWithSize(font: Font, nextSize: number): Font {
  const previousSize = font.size ?? DEFAULT_TEXT_FONT_SIZE;
  const lineHeight =
    font.lineHeight && previousSize > 0
      ? roundLayoutNumber(font.lineHeight * (nextSize / previousSize))
      : font.lineHeight;

  return {
    ...font,
    size: nextSize,
    lineHeight,
  };
}

function nextTextEditorFontFamily(currentFamily?: string | null) {
  const currentIndex = TEXT_EDITOR_FONT_FAMILIES.findIndex(
    (family) => family === currentFamily,
  );
  const nextIndex =
    currentIndex >= 0 ? (currentIndex + 1) % TEXT_EDITOR_FONT_FAMILIES.length : 0;

  return TEXT_EDITOR_FONT_FAMILIES[nextIndex];
}

function ComponentBounds({
  componentId,
  width,
  height,
}: {
  componentId: string;
  width: number;
  height: number;
}) {
  return (
    <Group listening={false}>
      <Rect
        width={width}
        height={height}
        stroke="rgba(34, 197, 94, 0.95)"
        strokeWidth={2}
      />
      <Text
        x={-10}
        y={-30}
        text={componentId}
        fill="#ffffff"
        fontFamily="Arial"
        fontSize={12}
        padding={4}
        fillAfterStrokeEnabled
        sceneFunc={(context, shape) => {
          const width = shape.width();
          const height = shape.height();
          context.beginPath();
          context.rect(0, 0, width, height);
          context.fillStrokeShape(shape);
        }}
      />
    </Group>
  );
}

function normalizeComponentRendererProps(props: ComponentRendererProps) {
  if ("component" in props) {
    return props;
  }

  const {
    isSelected,
    isElementSelectionActive,
    showBounds,
    showMissingImageMarkers,
    onSelect,
    onElementSelect,
    onComponentChange,
    ...component
  } = props;

  return {
    component,
    isSelected,
    isElementSelectionActive,
    showBounds,
    showMissingImageMarkers,
    onSelect,
    onElementSelect,
    onComponentChange,
  };
}

function nextElementSelection(
  elements: SlideElement[],
  point: Position,
  currentSelection: SelectedElement | null,
  rootFrame: Frame,
): SelectedElement | null {
  if (currentSelection && pointInFrame(point, currentSelection.frame)) {
    const childSelection = childSelectionAtPoint(
      currentSelection.element,
      point,
      currentSelection.frame,
      currentSelection.path,
    );

    if (childSelection) {
      return childSelection;
    }

    return currentSelection;
  }

  return elementSelectionAtPoint(
    elements,
    point,
    { x: 0, y: 0 },
    rootFrame,
    [],
    (index) => ({ kind: "root", index }),
    "absolute",
  );
}

function elementSelectionAtPoint(
  elements: SlideElement[],
  point: Position,
  origin: Position,
  parentFrame: Frame,
  pathPrefix: ElementPathSegment[],
  segmentForIndex: (index: number) => ElementPathSegment,
  layoutMode: SelectedElementLayoutMode,
): SelectedElement | null {
  for (let index = elements.length - 1; index >= 0; index -= 1) {
    const element = elements[index];
    const frame = absoluteFrame(elementFrame(element), origin);

    if (pointInFrame(point, frame)) {
      return {
        element,
        frame,
        parentFrame,
        path: [...pathPrefix, segmentForIndex(index)],
        layoutMode,
      };
    }
  }

  return null;
}

function childSelectionAtPoint(
  element: SlideElement,
  point: Position,
  frame: Frame,
  path: ElementPathSegment[],
): SelectedElement | null {
  if (element.type === "container" && element.child) {
    const childFrame = hasExplicitFrame(element.child)
      ? absoluteFrame(elementFrame(element.child), frame)
      : absoluteFrame(childFlowFrame(frame, element.padding), frame);

    return pointInFrame(point, childFrame)
      ? {
          element: element.child,
          frame: childFrame,
          parentFrame: frame,
          path: [...path, { kind: "child" }],
          layoutMode: "absolute",
        }
      : null;
  }

  if (element.type === "group") {
    return elementSelectionAtPoint(
      element.children,
      point,
      frame,
      frame,
      path,
      (index) => ({ kind: "children", index }),
      "absolute",
    );
  }

  if (element.type === "flex") {
    const childFrames = flexChildFrames(element.children, frame, element.direction, {
      gap: element.gap,
      columnGap: element.columnGap,
      rowGap: element.rowGap,
    });

    return childSelectionFromFrames(
      element.children,
      childFrames,
      point,
      frame,
      path,
      (index) => ({ kind: "children", index }),
      "layout-flow",
    );
  }

  if (element.type === "grid") {
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

    return childSelectionFromFrames(
      element.children,
      childFrames,
      point,
      frame,
      path,
      (index) => ({ kind: "children", index }),
      "layout-flow",
    );
  }

  if (element.type === "list-view") {
    const children = Array.from(
      { length: Math.max(0, Math.floor(element.count)) },
      () => element.item,
    );
    const childFrames = flexChildFrames(
      children,
      frame,
      element.direction ?? "column",
      {
        gap: element.gap,
        columnGap: element.columnGap,
        rowGap: element.rowGap,
      },
    );

    return childSelectionFromFrames(
      children,
      childFrames,
      point,
      frame,
      path,
      () => ({ kind: "item" }),
      "repeated-flow",
    );
  }

  if (element.type === "grid-view") {
    const count = Math.max(0, Math.floor(element.count));
    const children = Array.from({ length: count }, () => element.item);
    const childFrames = gridChildFrames(count, frame, element.columns, element.rows, {
      gap: element.gap,
      columnGap: element.columnGap,
      rowGap: element.rowGap,
    });

    return childSelectionFromFrames(
      children,
      childFrames,
      point,
      frame,
      path,
      () => ({ kind: "item" }),
      "repeated-flow",
    );
  }

  return null;
}

function childSelectionFromFrames(
  children: SlideElement[],
  childFrames: Frame[],
  point: Position,
  origin: Frame,
  pathPrefix: ElementPathSegment[],
  segmentForIndex: (index: number) => ElementPathSegment,
  layoutMode: SelectedElementLayoutMode,
) {
  for (let index = children.length - 1; index >= 0; index -= 1) {
    const localFrame =
      layoutMode === "repeated-flow"
        ? repeatedFlowChildFrame(children[index], childFrames[index])
        : layoutFlowChildFrame(children[index], childFrames[index]);
    const frame = absoluteFrame(localFrame, origin);

    if (pointInFrame(point, frame)) {
      return {
        element: children[index],
        frame,
        parentFrame:
          layoutMode === "repeated-flow"
            ? absoluteFrame(childFrames[index], origin)
            : origin,
        path: [...pathPrefix, segmentForIndex(index)],
        layoutMode,
      };
    }
  }

  return null;
}

function layoutFlowChildFrame(element: SlideElement, flowFrame: Frame): Frame {
  if (!isDetachedFlowElement(element)) {
    return flowFrame;
  }

  const position = elementPosition(element) ?? {
    x: flowFrame.x,
    y: flowFrame.y,
  };
  const size = elementSize(element);

  return {
    x: position.x,
    y: position.y,
    width: size?.width ?? flowFrame.width,
    height: size?.height ?? flowFrame.height,
  };
}

function repeatedFlowChildFrame(element: SlideElement, slotFrame: Frame): Frame {
  if (!isDetachedFlowElement(element)) {
    return slotFrame;
  }

  const position = elementPosition(element) ?? { x: 0, y: 0 };
  const size = elementSize(element);

  return {
    x: slotFrame.x + position.x,
    y: slotFrame.y + position.y,
    width: size?.width ?? slotFrame.width,
    height: size?.height ?? slotFrame.height,
  };
}

function isDetachedFlowElement(element: SlideElement) {
  return element.fixed === true && elementPosition(element) != null;
}

function selectedElementFrameFromNode(node: Konva.Rect | null): Frame | null {
  if (!node) {
    return null;
  }

  return {
    x: node.x(),
    y: node.y(),
    width: Math.max(node.width() * Math.abs(node.scaleX()), MIN_ELEMENT_WIDTH),
    height: Math.max(node.height() * Math.abs(node.scaleY()), MIN_ELEMENT_HEIGHT),
  };
}

function normalizeSelectedElementFrameNode(node: Konva.Rect | null, frame: Frame) {
  if (!node) {
    return;
  }

  node.x(frame.x);
  node.y(frame.y);
  node.width(frame.width);
  node.height(frame.height);
  node.scaleX(1);
  node.scaleY(1);
  node.getLayer()?.batchDraw();
}

function updateElementAtPath(
  elements: SlideElement[],
  path: ElementPathSegment[],
  updater: (element: SlideElement) => SlideElement,
): SlideElement[] {
  const [head, ...rest] = path;

  if (!head || head.kind !== "root") {
    return elements;
  }

  return elements.map((element, index) =>
    index === head.index ? updateElementNodeAtPath(element, rest, updater) : element,
  );
}

function updateElementNodeAtPath(
  element: SlideElement,
  path: ElementPathSegment[],
  updater: (element: SlideElement) => SlideElement,
): SlideElement {
  const [head, ...rest] = path;

  if (!head) {
    return updater(element);
  }

  if (head.kind === "child" && element.type === "container" && element.child) {
    return {
      ...element,
      child: updateElementNodeAtPath(element.child, rest, updater),
    };
  }

  if (head.kind === "children" && hasElementChildren(element)) {
    return {
      ...element,
      children: element.children.map((child, index) =>
        index === head.index ? updateElementNodeAtPath(child, rest, updater) : child,
      ),
    };
  }

  if (
    head.kind === "item" &&
    (element.type === "list-view" || element.type === "grid-view")
  ) {
    return {
      ...element,
      item: updateElementNodeAtPath(element.item, rest, updater),
    };
  }

  return element;
}

function hasElementChildren(
  element: SlideElement,
): element is Extract<SlideElement, { children: SlideElement[] }> {
  return element.type === "flex" || element.type === "grid" || element.type === "group";
}

function elementWithFrame(
  element: SlideElement,
  frame: Frame,
  parentFrame: Frame,
  layoutMode: SelectedElementLayoutMode,
): SlideElement {
  const nextElement = {
    ...element,
    position: {
      x: roundLayoutNumber(frame.x - parentFrame.x),
      y: roundLayoutNumber(frame.y - parentFrame.y),
    },
    size: {
      width: roundLayoutNumber(frame.width),
      height: roundLayoutNumber(frame.height),
    },
  };

  if (layoutMode === "layout-flow" || layoutMode === "repeated-flow") {
    return {
      ...nextElement,
      fixed: true,
    } as SlideElement;
  }

  return nextElement as SlideElement;
}

function roundLayoutNumber(value: number) {
  return Math.round(value * 100) / 100;
}

function elementFrame(element: SlideElement, flowFrame?: Frame): Frame {
  if (flowFrame) {
    return flowFrame;
  }

  const position = elementPosition(element);
  const size = elementSize(element);

  return {
    x: position?.x ?? 0,
    y: position?.y ?? 0,
    width: size?.width ?? 0,
    height: size?.height ?? 0,
  };
}

function absoluteFrame(frame: Frame, origin: Position): Frame {
  return {
    x: origin.x + frame.x,
    y: origin.y + frame.y,
    width: frame.width,
    height: frame.height,
  };
}

function pointInFrame(point: Position, frame: Frame) {
  return (
    point.x >= frame.x &&
    point.x <= frame.x + frame.width &&
    point.y >= frame.y &&
    point.y <= frame.y + frame.height
  );
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
  const gap =
    direction === "row" ? gaps.columnGap ?? gaps.gap ?? 0 : gaps.rowGap ?? gaps.gap ?? 0;
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
  const cellWidth = Math.max(
    (frame.width - columnGap * (columnCount - 1)) / columnCount,
    0,
  );
  const cellHeight = Math.max(
    (frame.height - rowGap * (rowCount - 1)) / rowCount,
    0,
  );

  return Array.from({ length: count }, (_, index) => ({
    x: (index % columnCount) * (cellWidth + columnGap),
    y: Math.floor(index / columnCount) * (cellHeight + rowGap),
    width: cellWidth,
    height: cellHeight,
  }));
}

function hasExplicitFrame(element: SlideElement) {
  return elementPosition(element) != null || elementSize(element) != null;
}

function elementPosition(element: SlideElement) {
  return "position" in element ? element.position ?? null : null;
}

function elementSize(element: SlideElement) {
  return "size" in element ? element.size ?? null : null;
}

function scaleElement(
  element: SlideElement,
  scaleX: number,
  scaleY: number,
): SlideElement {
  switch (element.type) {
    case "text":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        font: scaleFont(element.font, scaleY),
        stroke: scaleStroke(element.stroke, scaleX, scaleY),
        shadow: scaleShadow(element.shadow, scaleX, scaleY),
        runs: element.runs?.map((run) => ({
          ...run,
          font: scaleFont(run.font, scaleY),
        })),
      };
    case "container":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        stroke: scaleStroke(element.stroke, scaleX, scaleY),
        borderRadius: scaleBorderRadius(element.borderRadius, scaleX, scaleY),
        shadow: scaleShadow(element.shadow, scaleX, scaleY),
        padding: scalePadding(element.padding, scaleX, scaleY),
        child: element.child ? scaleElement(element.child, scaleX, scaleY) : element.child,
      };
    case "image":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        borderRadius: scaleBorderRadius(element.borderRadius, scaleX, scaleY),
      };
    case "text-list":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        font: scaleFont(element.font, scaleY),
      };
    case "table":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        columns: element.columns.map((cell) => ({
          ...cell,
          stroke: scaleStroke(cell.stroke, scaleX, scaleY),
        })),
        rows: element.rows.map((row) =>
          row.map((cell) => ({
            ...cell,
            stroke: scaleStroke(cell.stroke, scaleX, scaleY),
          })),
        ),
      };
    case "rectangle":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        stroke: scaleStroke(element.stroke, scaleX, scaleY),
        borderRadius: scaleBorderRadius(element.borderRadius, scaleX, scaleY),
        shadow: scaleShadow(element.shadow, scaleX, scaleY),
      };
    case "ellipse":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        stroke: scaleStroke(element.stroke, scaleX, scaleY),
        shadow: scaleShadow(element.shadow, scaleX, scaleY),
      };
    case "line":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        stroke: scaleStroke(element.stroke, scaleX, scaleY) ?? element.stroke,
        shadow: scaleShadow(element.shadow, scaleX, scaleY),
      };
    case "chart":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
      };
    case "flex":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY) ?? element.position,
        size: scaleSize(element.size, scaleX, scaleY) ?? element.size,
        gap: scaleOptional(element.gap, averageScale(scaleX, scaleY)),
        columnGap: scaleOptional(element.columnGap, scaleX),
        rowGap: scaleOptional(element.rowGap, scaleY),
        children: element.children.map((child) => scaleElement(child, scaleX, scaleY)),
      };
    case "grid":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY) ?? element.position,
        size: scaleSize(element.size, scaleX, scaleY) ?? element.size,
        gap: scaleOptional(element.gap, averageScale(scaleX, scaleY)),
        columnGap: scaleOptional(element.columnGap, scaleX),
        rowGap: scaleOptional(element.rowGap, scaleY),
        children: element.children.map((child) => scaleElement(child, scaleX, scaleY)),
      };
    case "list-view":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        gap: scaleOptional(element.gap, averageScale(scaleX, scaleY)),
        columnGap: scaleOptional(element.columnGap, scaleX),
        rowGap: scaleOptional(element.rowGap, scaleY),
        item: scaleElement(element.item, scaleX, scaleY),
      };
    case "grid-view":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY),
        size: scaleSize(element.size, scaleX, scaleY),
        gap: scaleOptional(element.gap, averageScale(scaleX, scaleY)),
        columnGap: scaleOptional(element.columnGap, scaleX),
        rowGap: scaleOptional(element.rowGap, scaleY),
        item: scaleElement(element.item, scaleX, scaleY),
      };
    case "group":
      return {
        ...element,
        position: scalePosition(element.position, scaleX, scaleY) ?? element.position,
        size: scaleSize(element.size, scaleX, scaleY) ?? element.size,
        children: element.children.map((child) => scaleElement(child, scaleX, scaleY)),
      };
  }
}

function scalePosition(
  position: Position | null | undefined,
  scaleX: number,
  scaleY: number,
) {
  return position ? { x: position.x * scaleX, y: position.y * scaleY } : position;
}

function scaleSize(size: Size | null | undefined, scaleX: number, scaleY: number) {
  return size ? { width: size.width * scaleX, height: size.height * scaleY } : size;
}

function scaleFont(font: Font | null | undefined, scale: number) {
  return font
    ? {
        ...font,
        size: scaleOptional(font.size, scale),
        lineHeight: scaleOptional(font.lineHeight, scale),
        letterSpacing: scaleOptional(font.letterSpacing, scale),
      }
    : font;
}

function scaleStroke(
  stroke: Stroke | null | undefined,
  scaleX: number,
  scaleY: number,
) {
  return stroke
    ? {
        ...stroke,
        width: stroke.width * averageScale(scaleX, scaleY),
        dash: stroke.dash?.map((value) => value * averageScale(scaleX, scaleY)),
      }
    : stroke;
}

function scaleBorderRadius(
  radius: BorderRadius | null | undefined,
  scaleX: number,
  scaleY: number,
) {
  const scale = averageScale(scaleX, scaleY);

  return radius
    ? {
        tl: radius.tl * scale,
        tr: radius.tr * scale,
        br: radius.br * scale,
        bl: radius.bl * scale,
      }
    : radius;
}

function scaleShadow(
  shadow: Shadow | null | undefined,
  scaleX: number,
  scaleY: number,
) {
  return shadow
    ? {
        ...shadow,
        blur: scaleOptional(shadow.blur, averageScale(scaleX, scaleY)),
        offsetX: scaleOptional(shadow.offsetX, scaleX),
        offsetY: scaleOptional(shadow.offsetY, scaleY),
      }
    : shadow;
}

function scalePadding(
  padding: Padding | null | undefined,
  scaleX: number,
  scaleY: number,
) {
  return padding
    ? {
        top: padding.top * scaleY,
        right: padding.right * scaleX,
        bottom: padding.bottom * scaleY,
        left: padding.left * scaleX,
      }
    : padding;
}

function scaleOptional(value: number | null | undefined, scale: number) {
  return value == null ? value : value * scale;
}

function averageScale(scaleX: number, scaleY: number) {
  return (scaleX + scaleY) / 2;
}
