from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    App configuration, loaded from environment variables / .env.
    """

    database_url: str = "postgresql+psycopg2://reliefiq:reliefiq@localhost:5432/reliefiq"
    app_env: str = "development"

    storage_dir: str = "./storage/documents"
    max_upload_size_mb: int = 25

    # --- Generation: primary provider + fallback chain ---
    # generation_provider is tried first; fallback_providers are tried in
    # order if it fails (or is in cooldown after a recent failure).
    #
    # fallback_providers is stored as a raw comma-separated string
    # (not list[str]) because pydantic-settings tries to JSON-decode
    # list-typed env vars before any validator runs, which would force
    # .env to use FALLBACK_PROVIDERS=["groq","openai"] JSON syntax.
    # Storing it as a string and parsing via the property below lets
    # .env just use the plain, easy-to-type form:
    #   FALLBACK_PROVIDERS=groq,openai
    generation_provider: str = "gemini"
    fallback_providers_raw: str = Field(default="groq", alias="FALLBACK_PROVIDERS")

    @property
    def fallback_providers(self) -> list[str]:
        return [
            item.strip()
            for item in self.fallback_providers_raw.split(",")
            if item.strip()
        ]

    gemini_api_key: str = ""
    generation_model: str = "gemini-2.5-flash"

    openai_api_key: str = ""
    openai_generation_model: str = "gpt-4o-mini"

    anthropic_api_key: str = ""
    anthropic_generation_model: str = "claude-sonnet-4-6"

    groq_api_key: str = ""
    groq_generation_model: str = "llama-3.3-70b-versatile"

    # --- Auth ---
    jwt_secret_key: str = "change-me-in-.env"  # override in .env, never commit a real one
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
