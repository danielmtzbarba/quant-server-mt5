import os


class Settings:
    MT5_PATH: str = os.environ.get(
        "MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe"
    )
    MT5_LOGIN: str = os.environ.get("MT5_LOGIN", "")
    MT5_PASSWORD: str = os.environ.get("MT5_PASSWORD", "")
    MT5_SERVER: str = os.environ.get("MT5_SERVER", "")


settings = Settings()
