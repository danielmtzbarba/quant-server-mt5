from common_config import BaseServiceSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseServiceSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    ADMIN_TOKEN: str = ""
    APP_URL: str = "http://localhost:3000"
    CORE_SERVICE_URL: str = "http://core-service:8001"
    MT5_SERVICE_URL: str = "http://mt5-service:8000"
    MESSAGING_SERVICE_URL: str = "http://messaging-service:8003"

    model_config = SettingsConfigDict(
        env_file=BaseServiceSettings.find_env_files("core", __file__),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
