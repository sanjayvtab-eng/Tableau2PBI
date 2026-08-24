from __future__ import annotations
import re
import hashlib
from pathlib import Path, PureWindowsPath
from app.core.name_sanitizer import clean_name
from app.models.schemas import MigrationProject, SourceMapping

LOCAL_CONNECTORS = {"CSV", "Text", "Excel", "JSON", "XML", "Parquet"}


def _looks_windows_absolute(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", value or "")) or str(value or "").startswith("\\\\")


def _looks_posix_absolute(value: str) -> bool:
    return str(value or "").startswith("/")


def is_absolute_path(value: str | None) -> bool:
    if not value:
        return False
    return _looks_windows_absolute(value) or _looks_posix_absolute(value)


def normalize_file_path(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip().strip('"')
    if not raw:
        return None
    if _looks_windows_absolute(raw) or raw.startswith("\\\\"):
        return str(PureWindowsPath(raw))
    return str(Path(raw).expanduser()) if _looks_posix_absolute(raw) else raw.replace("\\", "/")


def _physical_file_identity(mapping: SourceMapping) -> str:
    """Return a stable identity shared by every sheet/query from the same file."""
    value = mapping.target_file_path or mapping.detected_source_path or mapping.datasource or "Source"
    return normalize_file_path(value) or str(value)


def parameter_name(mapping: SourceMapping) -> str:
    """Create a collision-safe parameter name per physical file, not per sheet."""
    identity = _physical_file_identity(mapping)
    file_stem = Path(identity.replace("\\", "/")).stem if identity else "Source"
    base = clean_name(file_stem or mapping.datasource or "Source").replace(" ", "_")
    base = re.sub(r"[^A-Za-z0-9_]", "_", base).strip("_") or "Source"
    if base[0].isdigit():
        base = "T_" + base
    digest = hashlib.sha1(identity.casefold().encode("utf-8", errors="ignore")).hexdigest()[:8]
    return f"{base}_{digest}_SourcePath"


def _is_cloud_workspace_path(value: str | None, workspace: Path | None) -> bool:
    """Detect backend-only paths that must never be serialized as client Power BI paths."""
    if not value or not _looks_posix_absolute(value):
        return False
    normalized = str(Path(value))
    if normalized.startswith("/tmp/") or normalized.startswith("/var/tmp/"):
        return True
    if workspace is not None:
        try:
            Path(value).resolve().relative_to(workspace.resolve())
            return True
        except Exception:
            pass
    return False


def configure_mapping_path(mapping: SourceMapping, workspace: Path | None = None) -> SourceMapping:
    """Resolve one stable path parameter for local file connectors.

    Cloud/runtime workspace paths are useful for server-side profiling only and are never
    emitted as final Power BI client paths. An explicit user path always wins. Relative
    package paths may be retained as portable mapping hints, while the UI/validation can
    require the user to confirm the final client path after download.
    """
    if mapping.target_connector not in LOCAL_CONNECTORS:
        mapping.powerbi_path_parameter = None
        mapping.resolved_powerbi_path = None
        mapping.path_mode = "Not applicable"
        return mapping

    explicit = normalize_file_path(mapping.target_file_path)
    stored = normalize_file_path(mapping.resolved_powerbi_path)
    uploaded_abs = normalize_file_path(str(mapping.parameter_values.get("absolute_path") or ""))
    detected = normalize_file_path(mapping.detected_source_path)

    chosen: str | None = None
    mode = "Unresolved"

    # Explicit user mappings are the only absolute paths safe to carry across a cloud export.
    if explicit and is_absolute_path(explicit) and not _is_cloud_workspace_path(explicit, workspace):
        chosen, mode = explicit, "Explicit absolute path"
    elif stored and is_absolute_path(stored) and not _is_cloud_workspace_path(stored, workspace):
        chosen, mode = stored, "Resolved client absolute path"
    elif explicit and not is_absolute_path(explicit):
        # Keep the original relative package path as a portable hint. Do not rewrite it
        # to a Render/Linux /tmp path merely because that file exists on the backend.
        chosen, mode = explicit.replace("\\", "/"), "Portable relative path - confirm after download"
    elif detected and not is_absolute_path(detected):
        chosen, mode = detected.replace("\\", "/"), "Portable detected path - confirm after download"
    elif uploaded_abs and not _is_cloud_workspace_path(uploaded_abs, workspace):
        chosen, mode = uploaded_abs, "Uploaded client absolute path"
    elif detected and is_absolute_path(detected) and not _is_cloud_workspace_path(detected, workspace):
        chosen, mode = detected, "Detected client absolute path"
    else:
        mode = "Cloud workspace path suppressed - client path required"

    mapping.powerbi_path_parameter = parameter_name(mapping)
    mapping.resolved_powerbi_path = chosen
    mapping.path_mode = mode
    mapping.parameter_values["powerbi_path_parameter"] = mapping.powerbi_path_parameter
    mapping.parameter_values["resolved_powerbi_path"] = chosen or ""
    mapping.parameter_values["path_mode"] = mode
    mapping.parameter_values["requires_path_update_after_move"] = mode in {
        "Portable relative path - confirm after download",
        "Portable detected path - confirm after download",
        "Cloud workspace path suppressed - client path required",
    }
    return mapping


def configure_project_paths(project: MigrationProject) -> None:
    workspace = Path(project.workspace_path).resolve()
    for mapping in project.source_mappings:
        configure_mapping_path(mapping, workspace)
