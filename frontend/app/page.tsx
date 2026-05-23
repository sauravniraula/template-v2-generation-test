import Link from "next/link";
import { getTemplateSummaries } from "@/lib/templates";

export default function Home() {
  const templates = getTemplateSummaries();

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col justify-center gap-8 px-8 py-12">
        <div className="space-y-3">
          <p className="text-sm font-medium uppercase tracking-[0.16em] text-blue-700">
            Presentation Preview
          </p>
          <h1 className="text-4xl font-semibold tracking-normal">
            Select a template
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-slate-600">
            Available templates are loaded from the local templates directory.
          </p>
        </div>

        {templates.length > 0 ? (
          <div className="grid w-full gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {templates.map((template) => (
              <Link
                key={template.id}
                href={`/layout-preview?template=${encodeURIComponent(template.id)}`}
                className="rounded-md border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-blue-300 hover:bg-blue-50"
              >
                <span className="block text-lg font-semibold text-slate-950">
                  {template.name}
                </span>
                <span className="mt-2 block text-sm text-slate-600">
                  {template.layoutCount} layouts, {template.componentCount} components
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
            No templates found.
          </div>
        )}
      </div>
    </main>
  );
}
