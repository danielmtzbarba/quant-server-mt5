from common_config import BaseServiceSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseServiceSettings):
    MT5_SERVICE_URL: str = "http://mt5_service:8000"
    CORE_SERVICE_URL: str = "http://core_service:8001"
    BACKEND_URL: str = "http://mt5-engine-gcp:8002"
    MT5_LOGIN: str = ""

    INFLUX_URL: str = "http://localhost:8086"
    INFLUX_TOKEN: str = ""
    INFLUX_ORG: str = ""
    INFLUX_BUCKET: str = "tradedb"

    model_config = SettingsConfigDict(
        env_file=BaseServiceSettings.find_env_files("sync", __file__),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
