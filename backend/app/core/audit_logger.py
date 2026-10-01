from __future__ import annotations
import datetime
import json
import logging
from pathlib import Path
from typing import Any
from app.core.config import settings

logger = logging.getLogger("tableau2pbi.audit")

def _audit_file() -> Path:
    return settings.storage_root / "audit_log.jsonl"

def log_event(
    event_type: str,
    user_id: str | None = None,
    project_id: str | None = None,
    status: str = "SUCCESS",
    details: dict[str, Any] | None = None,
) -> None:
    """
    Safely append an audit record to the persistent audit log file.
    Failure to log an audit event will never interrupt or fail the core request.
    """
    try:
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id or "anonymous",
            "project_id": project_id,
            "status": status,
            "details": details or {},
        }
        file_path = _audit_file()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as exc:
        logger.warning(f"Failed to record audit log entry: {exc}")

def get_recent_audit_logs(limit: int = 100) -> list[dict[str, Any]]:
    """Retrieve the most recent audit log entries."""
    file_path = _audit_file()
    if not file_path.exists():
        return []
    entries = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries[-limit:]
    except Exception as exc:
        logger.warning(f"Failed to read audit logs: {exc}")
        return []
