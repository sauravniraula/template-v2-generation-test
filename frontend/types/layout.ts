import type { SlideComponent } from "./component";

export interface SlideLayout {
  id: string;
  description: string;
  components: SlideComponent[];
}

export interface SlideLayouts {
  layouts: SlideLayout[];
}
