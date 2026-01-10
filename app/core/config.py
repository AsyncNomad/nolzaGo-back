from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_prefix="NOLZAGO_")

    app_name: str = "nolzaGo"
    debug: bool = True
    root_path: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nolzago"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60 * 24
    allowed_hosts: list[str] = ["*"]
    kakao_rest_api_key: str | None = None
    kakao_map_rest_api_key: str | None = None
    gemini_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
