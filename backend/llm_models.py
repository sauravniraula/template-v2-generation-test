from typing import List, Optional

from pydantic import BaseModel, Field

from elements import Position, Size, SlideElement


class SlideComponent(BaseModel):
    id: str = Field(min_length=3, max_length=50)
    description: str = Field(min_length=20, max_length=200)
    position: Optional[Position] = None
    size: Optional[Size] = None
    elements: List[SlideElement] = Field(min_length=1)


class SlideComponents(BaseModel):
    components: List[SlideComponent] = Field(min_length=1)


class SlideLayout(BaseModel):
    id: str = Field(min_length=3, max_length=50)
    description: str = Field(min_length=20, max_length=200)
    components: List[SlideComponent] = Field(min_length=1)


class SlideLayouts(BaseModel):
    layouts: List[SlideLayout] = Field(min_length=1)
