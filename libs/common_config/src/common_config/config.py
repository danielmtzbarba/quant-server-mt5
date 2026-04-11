import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_env_var(
    name: str, default: Optional[str] = None, required: bool = False
) -> Optional[str]:
    """Retrieves an environment variable and optionally raises an error if missing."""
    load_dotenv()
    value = os.getenv(name, default)
    if required and value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


class BaseServiceSettings(BaseSettings):
    """
    Base settings class for all services with standardized .env priority.
    Priority order (highest to lowest):
    1. .env next to main.py
    2. infra/envs/<service_name>.env
    3. Root .env
    4. Environment variables
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def find_env_files(cls, service_name: str, main_file: str) -> List[Path]:
        """Builds the list of .env files based on priority."""
        paths = []
        app_root = Path(main_file).parent

        # 1. .env next to main.py
        local_env = app_root / ".env"
        if local_env.exists():
            paths.append(local_env)

        # Find workspace root (assume it contains 'infra' or '.git')
        workspace_root = Path(main_file).resolve()
        while workspace_root.parent != workspace_root:
            if (workspace_root / "infra").exists() or (
                workspace_root / ".git"
            ).exists():
                break
            workspace_root = workspace_root.parent

        # 2. infra/envs/<service_name>.env
        infra_env = workspace_root / "infra" / "envs" / f"{service_name}.env"
        if infra_env.exists():
            paths.append(infra_env)

        # 3. Root .env
        root_env = workspace_root / ".env"
        if root_env.exists() and root_env not in paths:
            paths.append(root_env)

        return paths
