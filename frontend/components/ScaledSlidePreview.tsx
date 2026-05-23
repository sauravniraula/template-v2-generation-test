"use client";

import { useEffect, useRef, useState } from "react";
import { SlideLayoutRenderer } from "@/components/SlideLayoutRenderer";
import type { SlideLayout } from "@/types/layout";
import type { CSSProperties } from "react";

const SLIDE_SIZE = {
  width: 1280,
  height: 720,
};

interface ScaledSlidePreviewProps {
  layout: SlideLayout;
  showComponentBounds?: boolean;
  showMissingImageMarkers?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function ScaledSlidePreview({
  layout,
  showComponentBounds = false,
  showMissingImageMarkers = true,
  className,
  style,
}: ScaledSlidePreviewProps) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const viewport = viewportRef.current;

    if (!viewport) {
      return;
    }

    const updateScale = () => {
      const nextScale = Math.min(1, viewport.clientWidth / SLIDE_SIZE.width);
      setScale(nextScale > 0 ? nextScale : 1);
    };

    updateScale();

    const resizeObserver = new ResizeObserver(updateScale);
    resizeObserver.observe(viewport);

    return () => resizeObserver.disconnect();
  }, []);

  return (
    <div
      ref={viewportRef}
      className={className}
      style={{
        width: "100%",
        maxWidth: SLIDE_SIZE.width,
        height: SLIDE_SIZE.height * scale,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: SLIDE_SIZE.width,
          height: SLIDE_SIZE.height,
          transform: `scale(${scale})`,
          transformOrigin: "top left",
        }}
      >
        <SlideLayoutRenderer
          layout={layout}
          width={SLIDE_SIZE.width}
          height={SLIDE_SIZE.height}
          showComponentBounds={showComponentBounds}
          showMissingImageMarkers={showMissingImageMarkers}
          style={style}
        />
      </div>
    </div>
  );
}
