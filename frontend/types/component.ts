import type { Nullable, Position, Size, SlideElement } from "./elements";

export interface SlideComponent {
  id: string;
  description: string;
  position?: Nullable<Position>;
  size?: Nullable<Size>;
  elements: SlideElement[];
}

export interface SlideComponents {
  components: SlideComponent[];
}
