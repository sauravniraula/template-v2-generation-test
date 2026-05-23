import { notFound } from "next/navigation";
import { LayoutPreviewClient } from "@/components/LayoutPreviewClient";
import {
  getTemplateLayouts,
  getTemplateSummaries,
  type TemplateSummary,
} from "@/lib/templates";

export const dynamic = "force-dynamic";

type TemplateSearchParams = {
  template?: string | string[];
};

interface LayoutPreviewPageProps {
  searchParams?: Promise<TemplateSearchParams>;
}

async function getSelectedTemplate(
  searchParams: LayoutPreviewPageProps["searchParams"],
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

export default async function LayoutPreviewPage({
  searchParams,
}: LayoutPreviewPageProps) {
  const template = await getSelectedTemplate(searchParams);
  const layouts = getTemplateLayouts(template.id);
  const componentsHref = `/components-preview?template=${encodeURIComponent(
    template.id,
  )}`;

  return (
    <LayoutPreviewClient
      templateName={template.name}
      layouts={layouts}
      componentsHref={componentsHref}
    />
  );
}
