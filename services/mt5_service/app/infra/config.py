import os
from dotenv import load_dotenv

# Standard path search for .env in the new structure
env_paths = [
    ".env",
    "infra/envs/shared.env",
    "infra/envs/mt5.env",
    os.path.join(os.path.dirname(__file__), "../../../../infra/envs/shared.env"),
    os.path.join(os.path.dirname(__file__), "../../../../infra/envs/mt5.env"),
]

for path in env_paths:
    if os.path.exists(path):
        load_dotenv(path)


class Settings:
    MT5_PATH: str = os.environ.get(
        "MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe"
    )
    MT5_LOGIN: str = os.environ.get("MT5_LOGIN", "")
    MT5_PASSWORD: str = os.environ.get("MT5_PASSWORD", "")
    MT5_SERVER: str = os.environ.get("MT5_SERVER", "")


settings = Settings()
