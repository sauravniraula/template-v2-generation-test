"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { SlideLayoutRenderer } from "@/components/SlideLayoutRenderer";
import type { SlideComponent } from "@/types/component";
import type { SlideElement } from "@/types/elements";
import type { SlideLayout } from "@/types/layout";

interface ComponentsPreviewProps {
  components: SlideComponent[];
}

const FALLBACK_COMPONENT_SIZE = {
  width: 320,
  height: 180,
};

const PREVIEW_SIZE = {
  width: 1280,
  height: 720,
};

export function ComponentsPreview({ components }: ComponentsPreviewProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const previewViewportRef = useRef<HTMLDivElement | null>(null);
  const [previewScale, setPreviewScale] = useState(1);
  const selected = components[selectedIndex] ?? components[0];
  const previewComponent = useMemo(
    () => (selected ? normalizeComponentForPreview(selected) : null),
    [selected],
  );
  const previewLayout = useMemo<SlideLayout | null>(() => {
    if (!previewComponent) {
      return null;
    }

    return {
      id: `${previewComponent.id}_preview`,
      description: previewComponent.descritpion,
      components: [previewComponent],
    };
  }, [previewComponent]);

  useEffect(() => {
    const viewport = previewViewportRef.current;

    if (!viewport) {
      return;
    }

    const updateScale = () => {
      const nextScale = Math.min(1, viewport.clientWidth / PREVIEW_SIZE.width);
      setPreviewScale(nextScale > 0 ? nextScale : 1);
    };

    updateScale();

    const resizeObserver = new ResizeObserver(updateScale);
    resizeObserver.observe(viewport);

    return () => resizeObserver.disconnect();
  }, []);

  if (!selected || !previewComponent || !previewLayout) {
    return (
      <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
        No components found.
      </div>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[400px_minmax(0,1fr)]">
      <aside className="max-h-[calc(100vh-180px)] overflow-y-auto rounded-md border border-slate-200 bg-white p-3 shadow-sm">
        <div className="grid gap-3">
          {components.map((component, index) => {
            const isSelected = index === selectedIndex;

            return (
              <button
                key={`${component.id}-${index}`}
                type="button"
                onClick={() => setSelectedIndex(index)}
                className={`rounded-md border p-4 text-left transition ${
                  isSelected
                    ? "border-blue-700 bg-blue-50 text-blue-950 shadow-sm"
                    : "border-slate-200 bg-white text-slate-900 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <span className="block text-sm font-semibold">{component.id}</span>
                <span
                  className={`mt-2 block text-sm leading-5 ${
                    isSelected ? "text-blue-800" : "text-slate-600"
                  }`}
                >
                  {component.descritpion}
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      <section className="min-w-0 space-y-4">
        <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-950">{selected.id}</h2>
          <p className="mt-1 text-sm text-slate-600">{selected.descritpion}</p>
          <dl className="mt-4 grid gap-3 text-sm text-slate-700 sm:grid-cols-2">
            <div>
              <dt className="text-slate-500">Position</dt>
              <dd>
                x: {previewComponent.position?.x ?? 0}, y:{" "}
                {previewComponent.position?.y ?? 0}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Size</dt>
              <dd>
                {previewComponent.size?.width ?? 0} x{" "}
                {previewComponent.size?.height ?? 0}
              </dd>
            </div>
          </dl>
        </div>

        <div className="overflow-hidden rounded-md border border-slate-200 bg-white p-4 shadow-sm">
          <div
            ref={previewViewportRef}
            className="w-full overflow-hidden"
            style={{
              height: PREVIEW_SIZE.height * previewScale,
            }}
          >
            <div
              className="origin-top-left"
              style={{
                width: PREVIEW_SIZE.width,
                height: PREVIEW_SIZE.height,
                transform: `scale(${previewScale})`,
                transformOrigin: "top left",
              }}
            >
              <SlideLayoutRenderer
                layout={previewLayout}
                width={PREVIEW_SIZE.width}
                height={PREVIEW_SIZE.height}
                showComponentBounds
                className="shrink-0"
                style={{
                  border: "1px solid #cbd5e1",
                  boxShadow: "0 18px 36px rgba(15, 23, 42, 0.08)",
                }}
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function normalizeComponentForPreview(component: SlideComponent): SlideComponent {
  return {
    ...component,
    position: component.position ?? { x: 0, y: 0 },
    size: component.size ?? inferComponentSize(component.elements),
  };
}

function inferComponentSize(elements: SlideElement[]) {
  const bounds = elements.reduce(
    (current, element) => {
      const position = "position" in element ? element.position : null;
      const size = "size" in element ? element.size : null;

      return {
        width: Math.max(
          current.width,
          (position?.x ?? 0) + (size?.width ?? 0),
        ),
        height: Math.max(
          current.height,
          (position?.y ?? 0) + (size?.height ?? 0),
        ),
      };
    },
    { width: 0, height: 0 },
  );

  return {
    width: bounds.width || FALLBACK_COMPONENT_SIZE.width,
    height: bounds.height || FALLBACK_COMPONENT_SIZE.height,
  };
}
