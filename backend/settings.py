from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str | None = None
    google_api_key: str
    google_openai_base_url: str = (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    class Config:
        env_file = ".env"


SETTINGS = Settings()
