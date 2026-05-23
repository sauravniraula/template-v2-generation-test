import Link from "next/link";
import { notFound } from "next/navigation";
import { ComponentsPreview } from "@/components/ComponentsPreview";
import {
  getTemplateComponents,
  getTemplateSummaries,
  type TemplateSummary,
} from "@/lib/templates";

export const dynamic = "force-dynamic";

type TemplateSearchParams = {
  template?: string | string[];
};

interface ComponentsPreviewPageProps {
  searchParams?: Promise<TemplateSearchParams>;
}

async function getSelectedTemplate(
  searchParams: ComponentsPreviewPageProps["searchParams"],
): Promise<TemplateSummary> {
  const params = searchParams ? await searchParams : undefined;
  const templateId = Array.isArray(params?.template)
    ? params.template[0]
    : params?.template;
  const templates = getTemplateSummaries();
  const template = templateId
    ? templates.find((candidate) => candidate.id === templateId)
    : templates[0];

  if (!template) {
    notFound();
  }

  return template;
}

export default async function ComponentsPreviewPage({
  searchParams,
}: ComponentsPreviewPageProps) {
  const template = await getSelectedTemplate(searchParams);
  const components = getTemplateComponents(template.id);
  const layoutsHref = `/layout-preview?template=${encodeURIComponent(template.id)}`;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="mx-auto flex w-full max-w-[1840px] flex-col gap-6 px-8 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">Components Preview</h1>
            <p className="text-sm text-slate-600">
              {template.name} - {components.length} reusable slide components
            </p>
          </div>
          <nav className="flex flex-wrap gap-3">
            <Link
              href="/"
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm hover:border-slate-400 hover:bg-slate-100"
            >
              Home
            </Link>
            <Link
              href={layoutsHref}
              className="rounded-md border border-blue-700 bg-blue-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:border-blue-600 hover:bg-blue-600"
            >
              View Layouts
            </Link>
          </nav>
        </header>

        <ComponentsPreview components={components} />
      </div>
    </main>
  );
}
