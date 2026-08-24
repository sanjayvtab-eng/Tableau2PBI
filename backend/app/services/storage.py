from __future__ import annotations
import re
import shutil
import uuid
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.json_utils import write_json, read_json
from app.models.schemas import MigrationProject


def _safe_filename(filename: str | None, fallback: str = "upload.bin") -> str:
    name = Path(filename or fallback).name
    name = re.sub(r"[^A-Za-z0-9._()\- ]+", "_", name).strip(" .")
    return name or fallback


def new_project_dir(project_name: str | None = None) -> tuple[str, Path]:
    project_id = uuid.uuid4().hex[:12]
    path = (settings.storage_root / project_id).resolve()
    (path / "uploads").mkdir(parents=True, exist_ok=True)
    (path / "extracted").mkdir(parents=True, exist_ok=True)
    (path / "exports").mkdir(parents=True, exist_ok=True)
    return project_id, path


def save_upload(project_path: Path, upload: UploadFile) -> Path:
    destination = (project_path / "uploads" / _safe_filename(upload.filename)).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as f:
        shutil.copyfileobj(upload.file, f, length=1024 * 1024)
    return destination


def persist_project(project: MigrationProject) -> None:
    write_json(Path(project.workspace_path).resolve() / "project.json", project.model_dump())


def load_project(project_id: str) -> MigrationProject:
    path = (settings.storage_root / project_id / "project.json").resolve()
    payload = read_json(path)
    if payload is None:
        raise FileNotFoundError(f"Project {project_id} not found")
    return MigrationProject.model_validate(payload)
