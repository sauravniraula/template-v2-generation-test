from typing import List

from pydantic import BaseModel, Field, model_validator

from elements import Position, Size, SlideElement

LOWER_SNAKE_CASE = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"


class SlideComponent(BaseModel):
    id: str = Field(min_length=3, max_length=50, pattern=LOWER_SNAKE_CASE)
    description: str = Field(min_length=20, max_length=200)
    position: Position
    size: Size
    elements: List[SlideElement] = Field(min_length=1)


class SlideLayout(BaseModel):
    id: str = Field(min_length=3, max_length=50, pattern=LOWER_SNAKE_CASE)
    description: str = Field(min_length=20, max_length=200)
    components: List[SlideComponent] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_component_ids(self):
        component_ids: set[str] = set()

        for component in self.components:
            if component.id in component_ids:
                raise ValueError(f"duplicate component id: {component.id}")
            component_ids.add(component.id)

        return self


class SlideLayouts(BaseModel):
    layouts: List[SlideLayout] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_layout_ids(self):
        layout_ids: set[str] = set()

        for layout in self.layouts:
            if layout.id in layout_ids:
                raise ValueError(f"duplicate layout id: {layout.id}")
            layout_ids.add(layout.id)

        return self
