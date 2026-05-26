import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import type { SlideComponent, SlideComponents } from "@/types/component";
import type { Position, Size, SlideElement } from "@/types/elements";
import type { SlideLayout, SlideLayouts } from "@/types/layout";

const TEMPLATES_DIR = path.join(process.cwd(), "app", "templates");
const IMAGE_MIME_TYPES: Record<string, string> = {
  ".gif": "image/gif",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
};

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
  return normalizeSlideLayouts(getLayouts(normalizeDescriptionKeys(data)));
}

export function getTemplateComponents(templateId: string): SlideComponent[] {
  const template = getTemplateSummary(templateId);

  if (!template) {
    throw new Error(`Unknown template: ${templateId}`);
  }

  const filePath = path.join(TEMPLATES_DIR, template.id, "components.json");

  if (!existsSync(filePath)) {
    return getComponentsFromLayouts(getTemplateLayouts(template.id));
  }

  const data = readJson(filePath);
  return normalizeComponents(getComponents(normalizeDescriptionKeys(data)));
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
    const layoutsPath = path.join(templatePath, "layouts.json");
    const layouts = getLayouts(normalizeDescriptionKeys(readJson(layoutsPath)));
    return getComponentsFromLayouts(layouts).length;
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

function getComponentsFromLayouts(layouts: SlideLayout[]): SlideComponent[] {
  const componentsById = new Map<string, SlideComponent>();

  for (const layout of layouts) {
    for (const component of layout.components) {
      if (!componentsById.has(component.id)) {
        componentsById.set(component.id, normalizeComponentFrame(component));
      }
    }
  }

  return Array.from(componentsById.values());
}

function normalizeSlideLayouts(layouts: SlideLayout[]): SlideLayout[] {
  return layouts.map((layout) => ({
    ...layout,
    components: normalizeComponents(layout.components),
  }));
}

function normalizeComponents(components: SlideComponent[]): SlideComponent[] {
  return components.map((component) => normalizeComponentFrame(component));
}

function normalizeComponentFrame(component: SlideComponent): SlideComponent {
  const elements = component.elements.map((element) =>
    normalizeElementImageSources(element),
  );
  const bounds = elementsBounds(elements);

  if (!bounds) {
    return {
      ...component,
      elements,
      position: component.position ?? { x: 0, y: 0 },
      size: component.size ?? { width: 0, height: 0 },
    };
  }

  const componentPosition = component.position ?? { x: 0, y: 0 };
  const elementsLookSlideLocal =
    component.position != null && positionsMatch(componentPosition, bounds);
  const nextPosition =
    component.position == null || elementsLookSlideLocal
      ? { x: bounds.x, y: bounds.y }
      : {
          x: componentPosition.x + bounds.x,
          y: componentPosition.y + bounds.y,
        };

  return {
    ...component,
    position: nextPosition,
    size: {
      width: bounds.width,
      height: bounds.height,
    },
    elements: elements.map((element) =>
      translateElement(element, -bounds.x, -bounds.y),
    ),
  };
}

interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

function elementsBounds(elements: SlideElement[]): Bounds | null {
  return elements.reduce<Bounds | null>(
    (current, element) => unionBounds(current, elementBounds(element)),
    null,
  );
}

function elementBounds(element: SlideElement): Bounds | null {
  const position = elementPosition(element) ?? { x: 0, y: 0 };
  const size = elementSize(element);

  if (size) {
    return {
      x: position.x,
      y: position.y,
      width: size.width,
      height: size.height,
    };
  }

  const nestedBounds = nestedElementBounds(element);

  if (!nestedBounds) {
    return null;
  }

  return {
    x: position.x + nestedBounds.x,
    y: position.y + nestedBounds.y,
    width: nestedBounds.width,
    height: nestedBounds.height,
  };
}

function nestedElementBounds(element: SlideElement): Bounds | null {
  if (element.type === "container") {
    return element.child ? elementBounds(element.child) : null;
  }

  if (element.type === "flex" || element.type === "grid" || element.type === "stack") {
    return elementsBounds(element.children);
  }

  if (element.type === "list-view") {
    return listViewBounds(element);
  }

  if (element.type === "grid-view") {
    return gridViewBounds(element);
  }

  return null;
}

function listViewBounds(
  element: Extract<SlideElement, { type: "list-view" }>,
): Bounds | null {
  const itemBounds = elementBounds(element.item);

  if (!itemBounds) {
    return null;
  }

  const count = Math.max(0, Math.floor(element.count));

  if (count === 0) {
    return { ...itemBounds, width: 0, height: 0 };
  }

  if ((element.direction ?? "column") === "row") {
    const gap = element.columnGap ?? element.gap ?? 0;

    return {
      x: itemBounds.x,
      y: itemBounds.y,
      width: itemBounds.width * count + gap * (count - 1),
      height: itemBounds.height,
    };
  }

  const gap = element.rowGap ?? element.gap ?? 0;

  return {
    x: itemBounds.x,
    y: itemBounds.y,
    width: itemBounds.width,
    height: itemBounds.height * count + gap * (count - 1),
  };
}

function gridViewBounds(
  element: Extract<SlideElement, { type: "grid-view" }>,
): Bounds | null {
  const itemBounds = elementBounds(element.item);

  if (!itemBounds) {
    return null;
  }

  const count = Math.max(0, Math.floor(element.count));

  if (count === 0) {
    return { ...itemBounds, width: 0, height: 0 };
  }

  const columns = Math.max(element.columns, 1);
  const rows = Math.max(element.rows ?? 0, Math.ceil(count / columns), 1);
  const columnGap = element.columnGap ?? element.gap ?? 0;
  const rowGap = element.rowGap ?? element.gap ?? 0;

  return {
    x: itemBounds.x,
    y: itemBounds.y,
    width: itemBounds.width * columns + columnGap * (columns - 1),
    height: itemBounds.height * rows + rowGap * (rows - 1),
  };
}

function translateElement(
  element: SlideElement,
  deltaX: number,
  deltaY: number,
): SlideElement {
  if (deltaX === 0 && deltaY === 0) {
    return element;
  }

  const position = elementPosition(element);

  if (position) {
    return {
      ...element,
      position: {
        x: position.x + deltaX,
        y: position.y + deltaY,
      },
    } as SlideElement;
  }

  if (element.type === "container" && element.child) {
    return {
      ...element,
      child: translateElement(element.child, deltaX, deltaY),
    };
  }

  if (element.type === "flex" || element.type === "grid" || element.type === "stack") {
    return {
      ...element,
      children: element.children.map((child) =>
        translateElement(child, deltaX, deltaY),
      ),
    };
  }

  if (element.type === "list-view" || element.type === "grid-view") {
    return {
      ...element,
      item: translateElement(element.item, deltaX, deltaY),
    };
  }

  return element;
}

function normalizeElementImageSources(element: SlideElement): SlideElement {
  if (element.type === "image") {
    return {
      ...element,
      data: inlineLocalImageSource(element.data),
    };
  }

  if (element.type === "container" && element.child) {
    return {
      ...element,
      child: normalizeElementImageSources(element.child),
    };
  }

  if (element.type === "flex" || element.type === "grid" || element.type === "stack") {
    return {
      ...element,
      children: element.children.map((child) => normalizeElementImageSources(child)),
    };
  }

  if (element.type === "list-view" || element.type === "grid-view") {
    return {
      ...element,
      item: normalizeElementImageSources(element.item),
    };
  }

  return element;
}

function inlineLocalImageSource(data?: string | null) {
  if (
    !data ||
    data.startsWith("data:") ||
    data.startsWith("http://") ||
    data.startsWith("https://")
  ) {
    return data;
  }

  if (!path.isAbsolute(data) || !existsSync(data) || !statSync(data).isFile()) {
    return data;
  }

  const extension = path.extname(data).toLowerCase();
  const mimeType = IMAGE_MIME_TYPES[extension] ?? "application/octet-stream";

  return `data:${mimeType};base64,${readFileSync(data).toString("base64")}`;
}

function elementPosition(element: SlideElement): Position | null {
  return "position" in element ? element.position ?? null : null;
}

function elementSize(element: SlideElement): Size | null {
  return "size" in element ? element.size ?? null : null;
}

function unionBounds(first: Bounds | null, second: Bounds | null): Bounds | null {
  if (!first) {
    return second;
  }

  if (!second) {
    return first;
  }

  const x = Math.min(first.x, second.x);
  const y = Math.min(first.y, second.y);
  const right = Math.max(first.x + first.width, second.x + second.width);
  const bottom = Math.max(first.y + first.height, second.y + second.height);

  return {
    x,
    y,
    width: right - x,
    height: bottom - y,
  };
}

function positionsMatch(position: Position, bounds: Bounds) {
  return nearlyEqual(position.x, bounds.x) && nearlyEqual(position.y, bounds.y);
}

function nearlyEqual(first: number, second: number) {
  return Math.abs(first - second) <= 1;
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
