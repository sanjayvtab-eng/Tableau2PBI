from __future__ import annotations
import os
import tempfile
from pathlib import Path
from pydantic_settings import BaseSettings


def _default_storage_root() -> Path:
    """Use a short runtime folder while allowing deployment storage to be overridden."""
    env = os.environ.get("T2PBI_WORKSPACE")
    if env:
        return Path(env).resolve()
    if os.name == "nt":
        try:
            return Path(r"C:\T2PBI_RUNTIME\workspace").resolve()
        except Exception:
            return (Path(tempfile.gettempdir()) / "T2PBI_RUNTIME" / "workspace").resolve()
    return (Path(tempfile.gettempdir()) / "t2pbi_runtime" / "workspace").resolve()


def _default_cors_origin_regex() -> str:
    return os.environ.get(
        "CORS_ORIGIN_REGEX",
        r"https?://(localhost|127\.0\.0\.1):\d+|https://[a-zA-Z0-9-]+\.onrender\.com",
    )


class Settings(BaseSettings):
    app_name: str = "TABLEAU2PBI Enterprise Migration Workbench"
    version: str = "11.6.7"
    storage_root: Path = _default_storage_root()
    max_upload_mb: int = 500
    safe_openable_mode: bool = True
    cors_origin_regex: str = _default_cors_origin_regex()
    auth_username: str | None = os.environ.get("T2PBI_AUTH_USERNAME")
    auth_password: str | None = os.environ.get("T2PBI_AUTH_PASSWORD")

    class Config:
        env_file = ".env"


settings = Settings()
settings.storage_root.mkdir(parents=True, exist_ok=True)
