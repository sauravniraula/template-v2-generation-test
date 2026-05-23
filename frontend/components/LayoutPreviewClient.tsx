"use client";

import Link from "next/link";
import { useState } from "react";
import { ScaledSlidePreview } from "@/components/ScaledSlidePreview";
import type { SlideLayout } from "@/types/layout";

interface LayoutPreviewClientProps {
  templateName: string;
  layouts: SlideLayout[];
  componentsHref: string;
}

export function LayoutPreviewClient({
  templateName,
  layouts,
  componentsHref,
}: LayoutPreviewClientProps) {
  const [showComponentBounds, setShowComponentBounds] = useState(true);
  const [showMissingImageMarkers, setShowMissingImageMarkers] = useState(true);

  return (
    <main className="h-screen overflow-y-auto bg-slate-50 text-slate-950">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-slate-50/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-[1440px] flex-wrap items-center justify-between gap-4 px-8 py-4">
          <div>
            <h1 className="text-2xl font-semibold">Layout Preview</h1>
            <p className="text-sm text-slate-600">
              {templateName} - {layouts.length} slide layouts
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-3">
            <Toggle
              checked={showComponentBounds}
              label="Component marks"
              onChange={setShowComponentBounds}
            />
            <Toggle
              checked={showMissingImageMarkers}
              label="Missing image marks"
              onChange={setShowMissingImageMarkers}
            />
            <nav className="flex flex-wrap gap-3">
              <Link
                href="/"
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm hover:border-slate-400 hover:bg-slate-100"
              >
                Home
              </Link>
              <Link
                href={componentsHref}
                className="rounded-md border border-blue-700 bg-blue-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:border-blue-600 hover:bg-blue-600"
              >
                View Components
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <section className="mx-auto flex w-full max-w-[1440px] flex-col items-center gap-10 px-8 py-8">
        {layouts.map((layout) => (
          <article key={layout.id} className="flex w-full flex-col items-center gap-3">
            <div className="w-full max-w-[1280px]">
              <h2 className="text-sm font-semibold text-slate-900">{layout.id}</h2>
              <p className="max-w-4xl text-sm text-slate-600">
                {layout.description}
              </p>
            </div>
            <ScaledSlidePreview
              layout={layout}
              showComponentBounds={showComponentBounds}
              showMissingImageMarkers={showMissingImageMarkers}
              className="mx-auto"
              style={{
                border: "1px solid #cbd5e1",
                boxShadow: "0 18px 36px rgba(15, 23, 42, 0.08)",
              }}
            />
          </article>
        ))}

        {layouts.length === 0 ? (
          <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
            No layouts found for this template.
          </div>
        ) : null}
      </section>
    </main>
  );
}

interface ToggleProps {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}

function Toggle({ checked, label, onChange }: ToggleProps) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="sr-only"
      />
      <span
        className={`relative h-5 w-9 rounded-full transition ${
          checked ? "bg-blue-700" : "bg-slate-300"
        }`}
        aria-hidden="true"
      >
        <span
          className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition ${
            checked ? "translate-x-4" : ""
          }`}
        />
      </span>
      <span>{label}</span>
    </label>
  );
}
