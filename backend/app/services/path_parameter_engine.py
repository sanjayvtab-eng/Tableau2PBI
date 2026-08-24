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
        # Keep Windows semantics even when backend validation runs on Linux.
        return str(PureWindowsPath(raw))
    return str(Path(raw).expanduser()) if _looks_posix_absolute(raw) else raw.replace("\\", "/")


def parameter_name(mapping: SourceMapping) -> str:
    base = clean_name(mapping.table_name or mapping.datasource or "Source").replace(" ", "_")
    base = re.sub(r"[^A-Za-z0-9_]", "_", base).strip("_") or "Source"
    if base[0].isdigit():
        base = "T_" + base
    digest = hashlib.sha1(str(mapping.source_id).encode("utf-8", errors="ignore")).hexdigest()[:6]
    return f"{base}_{digest}_SourcePath"


def configure_mapping_path(mapping: SourceMapping, workspace: Path | None = None) -> SourceMapping:
    """Resolve one stable file path and one M parameter for local file connectors.

    Priority is: user target path > previously resolved path > uploaded absolute path > detected path.
    No global SourceFolder parameter is created. Relative paths are never concatenated blindly.
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
    if explicit and is_absolute_path(explicit):
        chosen, mode = explicit, "Explicit absolute path"
    elif stored and is_absolute_path(stored):
        chosen, mode = stored, "Resolved absolute path"
    elif uploaded_abs and is_absolute_path(uploaded_abs):
        chosen, mode = uploaded_abs, "Uploaded workspace absolute path"
    elif explicit:
        # Resolve relative target path only against known files, never by blindly emitting the relative string.
        if workspace is not None:
            candidate = (workspace / explicit).resolve()
            if candidate.exists():
                chosen, mode = str(candidate), "Relative path resolved against project workspace"
            else:
                matches = [p.resolve() for p in workspace.rglob(Path(explicit).name) if p.is_file()]
                if len(matches) == 1:
                    chosen, mode = str(matches[0]), "Relative path matched to uploaded workspace file"
                elif len(matches) > 1:
                    # Packaged Tableau files may contain repeated copies of the same data asset.
                    # Prefer exact relative suffixes; if all candidates have identical bytes, select
                    # the shortest/canonical extracted path. Never choose between different contents.
                    norm = explicit.replace("\\", "/").lower()
                    exact = [p for p in matches if str(p).replace("\\", "/").lower().endswith(norm)] or matches
                    if len(exact) == 1:
                        chosen, mode = str(exact[0]), "Relative path suffix-matched to uploaded workspace file"
                    else:
                        import hashlib
                        digests = {}
                        for p in exact:
                            try:
                                digests.setdefault(hashlib.sha256(p.read_bytes()).hexdigest(), []).append(p)
                            except Exception:
                                pass
                        if len(digests) == 1 and digests:
                            canonical = sorted(next(iter(digests.values())), key=lambda x: (len(x.parts), len(str(x)), str(x)))[0]
                            chosen, mode = str(canonical), "Duplicate packaged copies matched; canonical uploaded workspace file selected"
        if chosen is None:
            mode = "Relative path requires final absolute mapping"
    elif detected:
        if is_absolute_path(detected):
            chosen, mode = detected, "Detected absolute path"
        elif workspace is not None:
            candidate = (workspace / detected).resolve()
            if candidate.exists():
                chosen, mode = str(candidate), "Detected relative path resolved against project workspace"

    mapping.powerbi_path_parameter = parameter_name(mapping)
    mapping.resolved_powerbi_path = chosen
    mapping.path_mode = mode
    mapping.parameter_values["powerbi_path_parameter"] = mapping.powerbi_path_parameter
    mapping.parameter_values["resolved_powerbi_path"] = chosen or ""
    mapping.parameter_values["path_mode"] = mode
    mapping.parameter_values["requires_path_update_after_move"] = mode == "Uploaded workspace absolute path"
    return mapping


def configure_project_paths(project: MigrationProject) -> None:
    workspace = Path(project.workspace_path).resolve()
    for mapping in project.source_mappings:
        configure_mapping_path(mapping, workspace)
