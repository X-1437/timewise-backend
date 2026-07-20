from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    _root_dir = Path(__file__).resolve().parent
    model_config = SettingsConfigDict(
        env_file=(_root_dir / ".env", _root_dir / ".env.example"),
        extra="ignore",
    )

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "timewise"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"


settings = Settings()
