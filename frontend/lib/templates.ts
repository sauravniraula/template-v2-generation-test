import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import type { SlideComponent, SlideComponents } from "@/types/component";
import type { SlideLayout, SlideLayouts } from "@/types/layout";

const TEMPLATES_DIR = path.join(process.cwd(), "app", "templates");

export interface TemplateSummary {
  id: string;
  name: string;
  layoutCount: number;
  componentCount: number;
}

export function getTemplateSummaries(): TemplateSummary[] {
  if (!existsSync(TEMPLATES_DIR)) {
    return [];
  }

  return readdirSync(TEMPLATES_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => templateSummary(entry.name))
    .filter((template): template is TemplateSummary => template !== null)
    .sort((first, second) => first.name.localeCompare(second.name));
}

export function getTemplateSummary(templateId: string): TemplateSummary | null {
  return (
    getTemplateSummaries().find((template) => template.id === templateId) ?? null
  );
}

export function getTemplateLayouts(templateId: string): SlideLayout[] {
  const data = readTemplateJson(templateId, "layouts.json");
  return getLayouts(normalizeDescriptionKeys(data));
}

export function getTemplateComponents(templateId: string): SlideComponent[] {
  const template = getTemplateSummary(templateId);

  if (!template) {
    throw new Error(`Unknown template: ${templateId}`);
  }

  const filePath = path.join(TEMPLATES_DIR, template.id, "components.json");

  if (!existsSync(filePath)) {
    return [];
  }

  const data = readJson(filePath);
  return getComponents(normalizeDescriptionKeys(data));
}

function templateSummary(templateId: string): TemplateSummary | null {
  const templatePath = path.join(TEMPLATES_DIR, templateId);
  const layoutsPath = path.join(templatePath, "layouts.json");

  if (!existsSync(layoutsPath)) {
    return null;
  }

  return {
    id: templateId,
    name: templateName(templateId),
    layoutCount: getLayouts(readJson(layoutsPath)).length,
    componentCount: componentCountForTemplate(templatePath),
  };
}

function componentCountForTemplate(templatePath: string) {
  const componentsPath = path.join(templatePath, "components.json");

  if (!existsSync(componentsPath)) {
    return 0;
  }

  return getComponents(normalizeDescriptionKeys(readJson(componentsPath))).length;
}

function readTemplateJson(templateId: string, fileName: string): unknown {
  const template = getTemplateSummary(templateId);

  if (!template) {
    throw new Error(`Unknown template: ${templateId}`);
  }

  const filePath = path.join(TEMPLATES_DIR, template.id, fileName);

  if (!existsSync(filePath) || !statSync(filePath).isFile()) {
    throw new Error(`Missing ${fileName} for template: ${template.id}`);
  }

  return readJson(filePath);
}

function readJson(filePath: string): unknown {
  return JSON.parse(readFileSync(filePath, "utf8"));
}

function getLayouts(value: unknown): SlideLayout[] {
  if (Array.isArray(value)) {
    return value as SlideLayout[];
  }

  if (isRecord(value) && Array.isArray(value.layouts)) {
    return (value as SlideLayouts).layouts;
  }

  return [];
}

function getComponents(value: unknown): SlideComponent[] {
  if (Array.isArray(value)) {
    return value as SlideComponent[];
  }

  if (isRecord(value) && Array.isArray(value.components)) {
    return (value as SlideComponents).components;
  }

  return [];
}

function normalizeDescriptionKeys(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeDescriptionKeys(item));
  }

  if (!isRecord(value)) {
    return value;
  }

  const normalized = Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      normalizeDescriptionKeys(item),
    ]),
  );

  if ("description" in normalized && !("descritpion" in normalized)) {
    normalized.descritpion = normalized.description;
  }

  if ("descritpion" in normalized && !("description" in normalized)) {
    normalized.description = normalized.descritpion;
  }

  return normalized;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function templateName(templateId: string) {
  return templateId
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
