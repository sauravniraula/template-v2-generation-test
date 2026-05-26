from fastapi import FastAPI

from generation_schema import create_layout_generation_schema
from llm_models import SlideLayout


app = FastAPI(title="Template V2 Backend")


@app.post("/layouts/generation-schema")
def layout_generation_schema(layout: SlideLayout):
    return create_layout_generation_schema(layout)
