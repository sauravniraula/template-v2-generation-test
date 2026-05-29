"use client";

import { useState } from "react";
import SlideRenderer from "@/components/SlideRenderer";
import type { SlideLayout } from "@/types/layout";

const DASHBOARD_IMAGE =
  "data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%20420%20260%27%3E%3Crect%20width%3D%27420%27%20height%3D%27260%27%20rx%3D%2728%27%20fill%3D%27%23111827%27/%3E%3Cpath%20d%3D%27M0%20210%20C85%20172%20122%20112%20208%20140%20C290%20166%20320%2058%20420%2036%20L420%20260%20L0%20260Z%27%20fill%3D%27%232563EB%27%20opacity%3D%27.72%27/%3E%3Ccircle%20cx%3D%27328%27%20cy%3D%2784%27%20r%3D%2752%27%20fill%3D%27%23F59E0B%27%20opacity%3D%27.9%27/%3E%3Crect%20x%3D%2740%27%20y%3D%2748%27%20width%3D%27188%27%20height%3D%2718%27%20rx%3D%279%27%20fill%3D%27%23F8FAFC%27%20opacity%3D%27.92%27/%3E%3Crect%20x%3D%2740%27%20y%3D%2784%27%20width%3D%27252%27%20height%3D%2710%27%20rx%3D%275%27%20fill%3D%27%23CBD5E1%27%20opacity%3D%27.88%27/%3E%3Crect%20x%3D%2740%27%20y%3D%27110%27%20width%3D%27216%27%20height%3D%2710%27%20rx%3D%275%27%20fill%3D%27%23CBD5E1%27%20opacity%3D%27.74%27/%3E%3C/svg%3E";

const INITIAL_LAYOUTS: SlideLayout[] = [
  {
    id: "slide_1",
    description: "Full slide layout converted from PPTX slide 1.",
    components: [
      {
        id: "slide_content",
        description:
          "Single component containing every element from PPTX slide 1.",
        position: {
          x: 0.0,
          y: 0.0,
        },
        size: {
          width: 1280.0,
          height: 720.0,
        },
        elements: [
          {
            type: "rectangle",
            fixed: true,
            position: {
              x: 0.0,
              y: 0.0,
            },
            size: {
              width: 1280.0,
              height: 720.0,
            },
            rotation: null,
            fill: {
              color: "#171717",
              opacity: null,
            },
            stroke: null,
            borderRadius: null,
            shadow: null,
          },
          {
            type: "rectangle",
            fixed: true,
            position: {
              x: 28.83,
              y: 161.54,
            },
            size: {
              width: 1222.34,
              height: 726.08,
            },
            rotation: null,
            fill: {
              color: "#D6FF3F",
              opacity: null,
            },
            stroke: null,
            borderRadius: null,
            shadow: null,
          },
          {
            type: "rectangle",
            fixed: true,
            position: {
              x: 325.03,
              y: 60.42,
            },
            size: {
              width: 204.73,
              height: 46.89,
            },
            rotation: null,
            fill: {
              color: "#000000",
              opacity: 0.0,
            },
            stroke: {
              color: "#D6FF3F",
              opacity: null,
              width: 1.33,
              dash: null,
            },
            borderRadius: null,
            shadow: null,
          },
          {
            type: "image",
            fixed: false,
            position: {
              x: 347.52,
              y: 69.81,
            },
            size: {
              width: 28.09,
              height: 28.11,
            },
            rotation: null,
            data: "pptx_assets/image1-84d34a93f326.png",
            name: "Freeform 9",
            fit: "fill",
            borderRadius: null,
            is_icon: null,
          },
          {
            type: "text",
            fixed: false,
            position: {
              x: 387.34,
              y: 70.15,
            },
            size: {
              width: 183.52,
              height: 25.42,
            },
            rotation: null,
            font: {
              size: 19.55,
              family: "Open Sauce",
              color: "#D6FF3F",
              bold: null,
              italic: null,
              lineHeight: null,
              letterSpacing: null,
              wrap: null,
              ellipsis: null,
            },
            alignment: {
              horizontal: "left",
              vertical: "top",
            },
            fill: null,
            stroke: null,
            shadow: null,
            runs: [
              {
                text: "Presentation",
                font: {
                  size: 19.55,
                  family: "Open Sauce",
                  color: "#D6FF3F",
                  bold: null,
                  italic: null,
                  lineHeight: null,
                  letterSpacing: null,
                  wrap: null,
                  ellipsis: null,
                },
              },
            ],
            maxLength: 12,
            minLength: 12,
          },
          {
            type: "line",
            fixed: true,
            position: {
              x: 550.38,
              y: 83.86,
            },
            size: {
              width: 557.17,
              height: 1.0,
            },
            rotation: null,
            stroke: {
              color: "#D6FF3F",
              opacity: null,
              width: 1.33,
              dash: null,
            },
            shadow: null,
          },
          {
            type: "rectangle",
            fixed: true,
            position: {
              x: 83.7,
              y: 60.42,
            },
            size: {
              width: 222.94,
              height: 46.89,
            },
            rotation: null,
            fill: {
              color: "#000000",
              opacity: 0.0,
            },
            stroke: {
              color: "#D6FF3F",
              opacity: null,
              width: 1.33,
              dash: null,
            },
            borderRadius: null,
            shadow: null,
          },
          {
            type: "text",
            fixed: false,
            position: {
              x: 89.72,
              y: 70.15,
            },
            size: {
              width: 210.89,
              height: 25.42,
            },
            rotation: null,
            font: {
              size: 19.55,
              family: "Open Sauce",
              color: "#D6FF3F",
              bold: null,
              italic: null,
              lineHeight: null,
              letterSpacing: null,
              wrap: null,
              ellipsis: null,
            },
            alignment: {
              horizontal: "center",
              vertical: "top",
            },
            fill: null,
            stroke: null,
            shadow: null,
            runs: [
              {
                text: "Paucek and Lage",
                font: {
                  size: 19.55,
                  family: "Open Sauce",
                  color: "#D6FF3F",
                  bold: null,
                  italic: null,
                  lineHeight: null,
                  letterSpacing: null,
                  wrap: null,
                  ellipsis: null,
                },
              },
            ],
            maxLength: 15,
            minLength: 15,
          },
          {
            type: "image",
            fixed: false,
            position: {
              x: 1153.53,
              y: 73.93,
            },
            size: {
              width: 19.86,
              height: 19.86,
            },
            rotation: null,
            data: "pptx_assets/image3-2c0c48d7cdf0.png",
            name: "Freeform 17",
            fit: "fill",
            borderRadius: null,
            is_icon: null,
          },
          {
            type: "image",
            fixed: false,
            position: {
              x: 1177.89,
              y: 73.93,
            },
            size: {
              width: 19.86,
              height: 19.86,
            },
            rotation: null,
            data: "pptx_assets/image5-f6e4b470ccc7.png",
            name: "Freeform 18",
            fit: "fill",
            borderRadius: null,
            is_icon: null,
          },
          {
            type: "image",
            fixed: false,
            position: {
              x: 1129.11,
              y: 73.93,
            },
            size: {
              width: 19.86,
              height: 19.86,
            },
            rotation: null,
            data: "pptx_assets/image3-2c0c48d7cdf0.png",
            name: "Freeform 19",
            fit: "fill",
            borderRadius: null,
            is_icon: null,
          },
          {
            type: "image",
            fixed: false,
            position: {
              x: 139.62,
              y: 386.9,
            },
            size: {
              width: 521.65,
              height: 510.74,
            },
            rotation: null,
            data: "pptx_assets/image7-1d24b100a254.jpeg",
            name: "Freeform 21",
            fit: "fill",
            borderRadius: null,
            is_icon: null,
          },
          {
            type: "rectangle",
            fixed: true,
            position: {
              x: 153.3,
              y: 402.17,
            },
            size: {
              width: 94.1,
              height: 94.1,
            },
            rotation: null,
            fill: {
              color: "#171717",
              opacity: null,
            },
            stroke: null,
            borderRadius: null,
            shadow: null,
          },
          {
            type: "image",
            fixed: false,
            position: {
              x: 176.97,
              y: 425.85,
            },
            size: {
              width: 46.76,
              height: 46.76,
            },
            rotation: null,
            data: "pptx_assets/image8-fab5295d79ea.png",
            name: "Freeform 25",
            fit: "fill",
            borderRadius: null,
            is_icon: null,
          },
          {
            type: "text",
            fixed: false,
            position: {
              x: 83.7,
              y: 227.13,
            },
            size: {
              width: 777.94,
              height: 159.78,
            },
            rotation: null,
            font: {
              size: 146.4,
              family: "Akzidenz-Grotesk Heavy",
              color: "#171717",
              bold: true,
              italic: null,
              lineHeight: null,
              letterSpacing: null,
              wrap: null,
              ellipsis: null,
            },
            alignment: {
              horizontal: "right",
              vertical: "top",
            },
            fill: null,
            stroke: null,
            shadow: null,
            runs: [
              {
                text: "CREATIVE  ",
                font: {
                  size: 146.4,
                  family: "Akzidenz-Grotesk Heavy",
                  color: "#171717",
                  bold: true,
                  italic: null,
                  lineHeight: null,
                  letterSpacing: null,
                  wrap: null,
                  ellipsis: null,
                },
              },
            ],
            maxLength: 10,
            minLength: 10,
          },
          {
            type: "text",
            fixed: false,
            position: {
              x: 734.92,
              y: 539.57,
            },
            size: {
              width: 414.06,
              height: 115.38,
            },
            rotation: null,
            font: {
              size: 15.11,
              family: "Open Sauce",
              color: "#171717",
              bold: null,
              italic: null,
              lineHeight: null,
              letterSpacing: null,
              wrap: null,
              ellipsis: null,
            },
            alignment: {
              horizontal: "left",
              vertical: "top",
            },
            fill: null,
            stroke: null,
            shadow: null,
            runs: [
              {
                text: "Presentations serve as versatile communication tools, utilized for demonstrations, lectures, speeches, reports, and more. Typically delivered before an audience, they fulfill various purposes, making presentations powerful tools for both persuasion and education.",
                font: {
                  size: 15.11,
                  family: "Open Sauce",
                  color: "#171717",
                  bold: null,
                  italic: null,
                  lineHeight: null,
                  letterSpacing: null,
                  wrap: null,
                  ellipsis: null,
                },
              },
            ],
            maxLength: 263,
            minLength: 263,
          },
          {
            type: "text",
            fixed: false,
            position: {
              x: 706.0,
              y: 383.79,
            },
            size: {
              width: 457.46,
              height: 159.78,
            },
            rotation: null,
            font: {
              size: 146.4,
              family: "Akzidenz-Grotesk Heavy",
              color: "#171717",
              bold: true,
              italic: null,
              lineHeight: null,
              letterSpacing: null,
              wrap: null,
              ellipsis: null,
            },
            alignment: {
              horizontal: "right",
              vertical: "top",
            },
            fill: null,
            stroke: null,
            shadow: null,
            runs: [
              {
                text: "BRIEF",
                font: {
                  size: 146.4,
                  family: "Akzidenz-Grotesk Heavy",
                  color: "#171717",
                  bold: true,
                  italic: null,
                  lineHeight: null,
                  letterSpacing: null,
                  wrap: null,
                  ellipsis: null,
                },
              },
            ],
            maxLength: 5,
            minLength: 5,
          },
        ],
      },
    ],
  },
];

interface LayoutHistory {
  past: SlideLayout[][];
  present: SlideLayout[];
  future: SlideLayout[][];
}

export default function App() {
  const [layoutHistory, setLayoutHistory] = useState<LayoutHistory>({
    past: [],
    present: INITIAL_LAYOUTS,
    future: [],
  });
  const [isStateModalOpen, setIsStateModalOpen] = useState(false);
  const [showComponentMarks, setShowComponentMarks] = useState(false);
  const layouts = layoutHistory.present;
  const currentLayout = layouts[0];
  const canUndo = layoutHistory.past.length > 0;
  const canRedo = layoutHistory.future.length > 0;

  const commitLayouts = (nextLayouts: SlideLayout[]) => {
    setLayoutHistory((currentHistory) => {
      if (currentHistory.present === nextLayouts) {
        return currentHistory;
      }

      return {
        past: [...currentHistory.past, currentHistory.present],
        present: nextLayouts,
        future: [],
      };
    });
  };

  const undoLayoutChange = () => {
    setLayoutHistory((currentHistory) => {
      const previous = currentHistory.past.at(-1);

      if (!previous) {
        return currentHistory;
      }

      return {
        past: currentHistory.past.slice(0, -1),
        present: previous,
        future: [currentHistory.present, ...currentHistory.future],
      };
    });
  };

  const redoLayoutChange = () => {
    setLayoutHistory((currentHistory) => {
      const next = currentHistory.future[0];

      if (!next) {
        return currentHistory;
      }

      return {
        past: [...currentHistory.past, currentHistory.present],
        present: next,
        future: currentHistory.future.slice(1),
      };
    });
  };

  return (
    <main className="min-h-screen overflow-auto bg-slate-100 px-8 py-10 text-slate-950">
      <div className="mx-auto flex w-full max-w-[1360px] flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">
              {currentLayout.description}
            </h1>
            <p className="text-sm text-slate-600">
              {currentLayout.components.length} renderer components
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsStateModalOpen(true)}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 shadow-sm hover:bg-slate-50"
          >
            Get current layout state
          </button>
          <label className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900 shadow-sm hover:bg-slate-50">
            <input
              type="checkbox"
              checked={showComponentMarks}
              onChange={(event) => setShowComponentMarks(event.target.checked)}
              className="h-4 w-4"
            />
            <span>Component marks</span>
          </label>
          <button
            type="button"
            onClick={undoLayoutChange}
            disabled={!canUndo}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
          >
            Undo
          </button>
          <button
            type="button"
            onClick={redoLayoutChange}
            disabled={!canRedo}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45"
          >
            Redo
          </button>
        </div>
        <SlideRenderer
          layout={currentLayout}
          showComponentBounds={showComponentMarks}
          onLayoutChange={(nextLayout) => {
            commitLayouts(
              layouts.map((layout) =>
                layout.id === nextLayout.id ? nextLayout : layout,
              ),
            );
          }}
        />
      </div>

      {isStateModalOpen ? (
        <div
          role="presentation"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/55 p-6"
          onClick={() => setIsStateModalOpen(false)}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="layout-state-title"
            className="flex max-h-[82vh] w-full max-w-5xl flex-col overflow-hidden rounded-md bg-white shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
              <h2 id="layout-state-title" className="text-base font-semibold">
                Current layouts
              </h2>
              <button
                type="button"
                onClick={() => setIsStateModalOpen(false)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Close
              </button>
            </header>
            <pre className="overflow-auto bg-slate-950 p-5 text-xs leading-5 text-slate-100">
              {JSON.stringify(layouts, null, 2)}
            </pre>
          </section>
        </div>
      ) : null}
    </main>
  );
}
