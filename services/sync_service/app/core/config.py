import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Standard path search for .env
env_paths = [
    ".env",
    "infra/envs/mt5_service.env",
    os.path.join(os.path.dirname(__file__), "../../../../infra/envs/mt5_service.env"),
]

for path in env_paths:
    if os.path.exists(path):
        load_dotenv(path)
        break


class Settings(BaseSettings):
    MT5_SERVICE_URL: str = os.environ.get("MT5_SERVICE_URL", "http://mt5_service:8000")
    BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://mt5-engine-gcp:8002")
    MT5_LOGIN: str = os.environ.get("MT5_LOGIN", "")

    INFLUX_URL: str = os.environ.get("INFLUX_URL", "http://localhost:8086")
    INFLUX_TOKEN: str = os.environ.get("INFLUX_TOKEN", "")
    INFLUX_ORG: str = os.environ.get("INFLUX_ORG", "")
    INFLUX_BUCKET: str = os.environ.get("INFLUX_BUCKET", "tradedb")

    class Config:
        case_sensitive = True


settings = Settings()
