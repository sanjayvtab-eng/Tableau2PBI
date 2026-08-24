from __future__ import annotations
import os
import tempfile
from pathlib import Path
from pydantic_settings import BaseSettings


def _default_storage_root() -> Path:
    """
    Use a short absolute runtime folder by default.
    Keeping workspace under the application folder caused Windows path length issues when
    the app was extracted under paths like C:\\Projects\\Tableau Project\\....
    """
    env = os.environ.get("T2PBI_WORKSPACE")
    if env:
        return Path(env).resolve()
    if os.name == "nt":
        # C:\T2PBI_RUNTIME is intentionally short. If C: is unavailable, fall back to TEMP.
        try:
            return Path(r"C:\T2PBI_RUNTIME\workspace").resolve()
        except Exception:
            return (Path(tempfile.gettempdir()) / "T2PBI_RUNTIME" / "workspace").resolve()
    return (Path(tempfile.gettempdir()) / "t2pbi_runtime" / "workspace").resolve()


def _default_cors_origin_regex() -> str:
    # Local development plus Render default domains. For custom domains, set CORS_ORIGIN_REGEX in Render.
    return os.environ.get(
        "CORS_ORIGIN_REGEX",
        r"https?://(localhost|127\.0\.0\.1):\d+|https://[a-zA-Z0-9-]+\.onrender\.com"
    )


class Settings(BaseSettings):
    app_name: str = "TABLEAU2PBI Enterprise Migration Workbench"
    version: str = "11.6.5"
    storage_root: Path = _default_storage_root()
    max_upload_mb: int = 500
    safe_openable_mode: bool = True
    cors_origin_regex: str = _default_cors_origin_regex()

    class Config:
        env_file = ".env"


settings = Settings()
settings.storage_root.mkdir(parents=True, exist_ok=True)
