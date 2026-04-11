from common_config import BaseServiceSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseServiceSettings):
    MT5_PATH: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    MT5_LOGIN: str = ""
    MT5_PASSWORD: str = ""
    MT5_SERVER: str = ""

    model_config = SettingsConfigDict(
        env_file=BaseServiceSettings.find_env_files("mt5", __file__),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
