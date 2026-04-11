from common_config import BaseServiceSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseServiceSettings):
    CORE_SERVICE_URL: str = "http://core_service:8001"
    EXECUTION_SERVICE_URL: str = "http://execution_service:8002"

    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_AUTH_TOKEN: str = "danielmtzbarba"
    ADMIN_TOKEN: str = "danielmtzbarba"
    WHATSAPP_URL: str = "https://graph.facebook.com/v17.0/142601282278212/messages"

    # LLM Providers
    LLM_PROVIDER: str = "OPENAI"
    OPENAI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=BaseServiceSettings.find_env_files("messaging", __file__),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
