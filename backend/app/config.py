from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Invoice Recognition API"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://invoice_user:invoice_password@localhost:55432/invoice_recognition"
    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_content_types: dict[str, str] = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    auth_disabled: bool = False
    keycloak_issuer: str = "http://localhost:8080/realms/Invoice-system"
    keycloak_jwks_url: str | None = None
    keycloak_audience: str = "invoice-client"
    frontend_origin: str = "http://localhost:5173"
    llm_provider: str = "mock"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    discord_bot_token: str | None = None
    discord_max_reply_chars: int = 1900

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
