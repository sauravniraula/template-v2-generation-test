"use client";

import ComponentRenderer from "@/components/ComponentRenderer";
import { useEffect, useRef, useState } from "react";
import { Layer, Stage } from "react-konva";
import type Konva from "konva";
import type { SlideLayout } from "@/types/layout";

export const DEFAULT_SLIDE_WIDTH = 1280;
export const DEFAULT_SLIDE_HEIGHT = 720;

export type SlideRendererProps =
  | {
      layout: SlideLayout;
      width?: number;
      height?: number;
      showComponentBounds?: boolean;
      showMissingImageMarkers?: boolean;
      onLayoutChange?: (layout: SlideLayout) => void;
    }
  | (SlideLayout & {
      width?: number;
      height?: number;
      showComponentBounds?: boolean;
      showMissingImageMarkers?: boolean;
      onLayoutChange?: (layout: SlideLayout) => void;
    });

export default function SlideRenderer(props: SlideRendererProps) {
  const {
    layout,
    width = DEFAULT_SLIDE_WIDTH,
    height = DEFAULT_SLIDE_HEIGHT,
    showComponentBounds = false,
    showMissingImageMarkers = true,
    onLayoutChange,
  } = normalizeSlideRendererProps(props);
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const [elementSelectionComponentId, setElementSelectionComponentId] = useState<
    string | null
  >(null);
  const stageRef = useRef<Konva.Stage>(null);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const stageContainer = stageRef.current?.container();

      if (
        stageContainer &&
        event.target instanceof Node &&
        !stageContainer.contains(event.target)
      ) {
        setSelectedComponentId(null);
        setElementSelectionComponentId(null);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, []);

  return (
    <Stage
      ref={stageRef}
      width={width}
      height={height}
      aria-label={layout.description || layout.id}
      onMouseDown={(event) => {
        if (isTransformerTarget(event.target)) {
          return;
        }

        const pointer = event.target.getStage()?.getPointerPosition();
        const component = pointer
          ? componentAtPoint(layout.components, pointer.x, pointer.y)
          : null;

        if (component) {
          setSelectedComponentId(component.id);
          setElementSelectionComponentId(null);
        }
      }}
      onTouchStart={(event) => {
        if (isTransformerTarget(event.target)) {
          return;
        }

        const pointer = event.target.getStage()?.getPointerPosition();
        const component = pointer
          ? componentAtPoint(layout.components, pointer.x, pointer.y)
          : null;

        if (component) {
          setSelectedComponentId(component.id);
          setElementSelectionComponentId(null);
        }
      }}
    >
      <Layer>
        {layout.components.map((component, index) => (
          <ComponentRenderer
            key={`${component.id}-${index}`}
            component={component}
            isSelected={selectedComponentId === component.id}
            isElementSelectionActive={elementSelectionComponentId === component.id}
            showBounds={showComponentBounds}
            showMissingImageMarkers={showMissingImageMarkers}
            onSelect={() => {
              setSelectedComponentId(component.id);
              setElementSelectionComponentId(null);
            }}
            onElementSelect={() => {
              setSelectedComponentId(null);
              setElementSelectionComponentId(component.id);
            }}
            onComponentChange={(nextComponent) => {
              onLayoutChange?.({
                ...layout,
                components: layout.components.map((item, itemIndex) =>
                  itemIndex === index ? nextComponent : item,
                ),
              });
            }}
          />
        ))}
      </Layer>
    </Stage>
  );
}

export { SlideRenderer };

function normalizeSlideRendererProps(props: SlideRendererProps) {
  if ("layout" in props) {
    return props;
  }

  const {
    width,
    height,
    showComponentBounds,
    showMissingImageMarkers,
    onLayoutChange,
    ...layout
  } = props;

  return {
    layout,
    width,
    height,
    showComponentBounds,
    showMissingImageMarkers,
    onLayoutChange,
  };
}

function componentAtPoint(
  components: SlideLayout["components"],
  x: number,
  y: number,
) {
  return components.findLast((component) => {
    const position = component.position ?? { x: 0, y: 0 };
    const size = component.size ?? { width: 0, height: 0 };

    return (
      x >= position.x &&
      x <= position.x + size.width &&
      y >= position.y &&
      y <= position.y + size.height
    );
  });
}

function isTransformerTarget(target: {
  getParent: () => unknown;
  getClassName?: () => string;
}) {
  let node: unknown = target;

  while (isKonvaNode(node)) {
    if (node.getClassName?.() === "Transformer") {
      return true;
    }

    node = node.getParent();
  }

  return false;
}

function isKonvaNode(value: unknown): value is {
  getParent: () => unknown;
  getClassName?: () => string;
} {
  return typeof value === "object" && value !== null && "getParent" in value;
}
