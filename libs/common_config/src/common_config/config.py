import os
from dotenv import load_dotenv


def get_env_var(name: str, default: str = None, required: bool = False) -> str:
    """Retrieves an environment variable and optionally raises an error if missing."""
    load_dotenv()
    value = os.getenv(name, default)
    if required and value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    return value
