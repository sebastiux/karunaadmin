"""Application configuration loaded from environment variables.

On Railway, set these as service variables. Locally, a `.env` file is read
(see `.env.example`). Sensible defaults let the app boot for local dev.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database -----------------------------------------------------------
    # Railway MySQL exposes MYSQL_URL / DATABASE_URL. We accept either.
    database_url: str = "mysql+pymysql://root:root@localhost:3306/karunaadmin"

    # --- Auth ---------------------------------------------------------------
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    # Bootstrap admin (created on first run if no users exist)
    admin_email: str = "admin@karuna.app"
    admin_password: str = "admin123"
    admin_name: str = "Administrator"

    # --- Grok / xAI ---------------------------------------------------------
    grok_api_key: str = ""  # empty => AI service runs in deterministic mock mode
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: str = "grok-4.3"

    # --- CORS / frontend ----------------------------------------------------
    # Comma-separated list of allowed origins. "*" allows all (dev only).
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def normalized_database_url(self) -> str:
        """Railway often provides a bare `mysql://` URL. SQLAlchemy needs the
        pymysql driver prefix, so we normalize it here."""
        url = self.database_url
        if url.startswith("mysql://"):
            url = url.replace("mysql://", "mysql+pymysql://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
