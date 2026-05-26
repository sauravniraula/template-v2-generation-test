from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None
    openrouter_base_url: str | None = None
    google_api_key: str | None = None
    google_openai_base_url: str = (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    class Config:
        env_file = ".env"


SETTINGS = Settings()
