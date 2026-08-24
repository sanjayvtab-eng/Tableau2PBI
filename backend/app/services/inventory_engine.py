from __future__ import annotations
import hashlib
import shutil
import zipfile
from pathlib import Path
from app.models.schemas import FileInventoryItem

ROLE_BY_EXT = {
    ".twb": "Workbook",
    ".twbx": "Packaged workbook",
    ".tds": "Data source",
    ".tdsx": "Packaged data source",
    ".hyper": "Hyper extract",
    ".tde": "Legacy TDE extract",
    ".tfl": "Prep flow",
    ".tflx": "Packaged Prep flow",
    ".csv": "Local source file",
    ".xlsx": "Local source file",
    ".xls": "Local source file",
    ".txt": "Local source file",
    ".tsv": "Local source file",
    ".json": "Local source file",
    ".xml": "Local source file",
    ".parquet": "Local source file",
    ".sql": "Custom SQL file",
    ".pdf": "PDF asset / metadata only",
    ".png": "Image/background asset",
    ".jpg": "Image/background asset",
    ".jpeg": "Image/background asset",
    ".gif": "Image/background asset",
    ".zip": "Complete Tableau project package",
}

PACKAGE_EXTENSIONS = {".zip", ".twbx", ".tdsx", ".tflx"}
PARSEABLE_EXTENSIONS = {".twb", ".tds", ".tfl", ".csv", ".xlsx", ".xls", ".json", ".xml", ".txt", ".tsv", ".parquet", ".hyper", ".sql"}


def role_for(path: Path) -> str:
    return ROLE_BY_EXT.get(path.suffix.lower(), "Unknown/manual review")


def _hash(value: str, n: int = 10) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:n]


def _safe_segment(segment: str, max_len: int = 42) -> str:
    """Make one ZIP path segment safe and short for Windows."""
    segment = segment.replace("\\", "_").replace("/", "_").strip(" .") or "item"
    # avoid Windows reserved filename characters
    safe = "".join(ch if ch not in '<>:"|?*' and ord(ch) >= 32 else "_" for ch in segment)
    p = Path(safe)
    suffix = p.suffix if len(p.suffix) <= 12 else ""
    stem = p.stem if suffix else safe
    if len(safe) > max_len:
        safe = f"{stem[:max_len-len(suffix)-11]}_{_hash(segment, 8)}{suffix}"
    return safe


def _short_package_dir(path: Path, prefix: str = "pkg") -> str:
    # Very short package directories prevent Windows MAX_PATH failures even if the app is extracted in a long path.
    return f"{prefix}_{_hash(str(path.resolve()) + path.name, 10)}"


def _normal_member_name(name: str) -> Path | None:
    clean = name.replace("\\", "/").strip("/")
    if not clean or clean.endswith("/"):
        return None
    parts = [part for part in clean.split("/") if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise ValueError(f"Unsafe path inside package: {name}")
    # Keep hierarchy, but shorten every segment. This is the key fix for Windows path-too-long issues.
    return Path(*[_safe_segment(part) for part in parts])


def _safe_extract(zf: zipfile.ZipFile, target_dir: Path) -> list[Path]:
    """Extract package safely and return files actually written. Never uses extractall."""
    root = target_dir.resolve()
    written: list[Path] = []
    for member in zf.infolist():
        rel = _normal_member_name(member.filename)
        if rel is None:
            continue
        dest = (root / rel).resolve()
        if not str(dest).lower().startswith(str(root).lower()):
            raise ValueError(f"Unsafe path inside package: {member.filename}")
        if member.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member, "r") as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out, length=1024 * 1024)
        written.append(dest)
    return written


def _copy_non_package(upload_path: Path, extract_root: Path) -> list[Path]:
    target = (extract_root / _safe_segment(upload_path.name, 64)).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if upload_path.resolve() != target:
        shutil.copy2(upload_path, target)
    return [target]


def list_zip_members_as_inventory(upload_path: Path, workspace_path: Path, reason: str) -> list[FileInventoryItem]:
    """
    Last-resort ZIP inventory fallback: even if extraction fails on a Windows machine,
    the user still sees the complete package content instead of only the uploaded ZIP.
    These entries are marked virtual, so parser/export can continue safely with warnings.
    """
    items: list[FileInventoryItem] = []
    try:
        with zipfile.ZipFile(upload_path) as zf:
            for info in zf.infolist():
                rel = _normal_member_name(info.filename)
                if rel is None or info.is_dir():
                    continue
                item = FileInventoryItem(
                    file_name=Path(info.filename.replace('\\', '/')).name,
                    extension=Path(info.filename).suffix.lower(),
                    folder_path=str(Path(info.filename.replace('\\', '/')).parent),
                    absolute_path=f"zip://{upload_path.resolve()}!/{info.filename}",
                    size_bytes=info.file_size,
                    role=ROLE_BY_EXT.get(Path(info.filename).suffix.lower(), "Unknown/manual review"),
                    parsed_status="Virtual inventory only",
                    warnings=[f"ZIP member listed without extraction because: {reason}"],
                )
                items.append(item)
    except Exception:
        pass
    return items


def extract_package(upload_path: Path, extract_root: Path, depth: int = 0, max_depth: int = 4) -> list[Path]:
    """
    Extract ZIP/TWBX/TDSX/TFLX recursively using short hashed folders.
    This prevents the exact issue where a valid package shows only one ZIP row because
    Windows path length blocks extraction under a long application folder.
    """
    upload_path = upload_path.resolve()
    extract_root = extract_root.resolve()
    suffix = upload_path.suffix.lower()
    if suffix not in PACKAGE_EXTENSIONS or depth > max_depth:
        return _copy_non_package(upload_path, extract_root)

    prefix = "pkg" if depth == 0 else "n"
    target_dir = (extract_root / _short_package_dir(upload_path, prefix)).resolve()
    if target_dir.exists() and depth == 0:
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(upload_path) as zf:
        paths = _safe_extract(zf, target_dir)

    all_paths = list(paths)
    for p in list(paths):
        if p.suffix.lower() in PACKAGE_EXTENSIONS and depth < max_depth:
            nested_root = target_dir / f"u_{_hash(str(p.resolve()), 8)}"
            try:
                all_paths.extend(extract_package(p, nested_root, depth=depth + 1, max_depth=max_depth))
            except Exception:
                # Keep nested package itself in inventory; do not block whole upload.
                continue
    return all_paths


def _relative_path(path: Path, workspace_path: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_path.resolve()))
    except ValueError:
        return path.name


def _is_json_xml_support_artifact(path: Path, rel: str) -> bool:
    if path.suffix.lower() not in {'.json', '.xml'}:
        return False
    low_name = path.name.lower().replace('-', '_').replace('.', '_')
    parts = {p.lower() for p in Path(rel).parts}
    support_dirs = {'metadata','meta','docs','documentation','assets','config','configuration','settings','validation','lineage','reports','migration_strategy','manual_review','source_mapping'}
    support_tokens = ('_meta_', '_metadata_', 'manifest', 'lineage', 'validation', 'reconciliation', 'recovery_plan', 'source_recovery', 'project_json', 'settings_json', 'config_json')
    return bool(parts & support_dirs) or any(t in low_name for t in support_tokens)


def build_inventory(files: list[Path], workspace_path: Path) -> list[FileInventoryItem]:
    inventory: list[FileInventoryItem] = []
    seen: set[str] = set()
    for path in sorted(files, key=lambda p: str(p).lower()):
        path = Path(path).resolve()
        if not path.exists() or not path.is_file():
            continue
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        rel = _relative_path(path, workspace_path)
        is_support = _is_json_xml_support_artifact(path, rel)
        item = FileInventoryItem(
            file_name=path.name,
            extension=path.suffix.lower(),
            folder_path=str(Path(rel).parent),
            absolute_path=str(path),
            size_bytes=path.stat().st_size,
            role=("TDE metadata companion" if path.name.lower().endswith((".tde.meta.json", "_tde_logic.json", "extract_lineage.json")) else ("Metadata/support file - not model table" if is_support else role_for(path))),
            parsed_status=("Inventory only" if is_support else ("Ready for parse" if path.suffix.lower() in PARSEABLE_EXTENSIONS else "Inventory only")),
        )
        lower_parts = [part.lower() for part in Path(rel).parts]
        if any("extract" in part for part in lower_parts) or item.extension in {".hyper", ".tde"}:
            item.associated_extract_or_source = path.name
        if path.suffix.lower() in {".twb", ".twbx"}:
            item.associated_workbook = path.stem
        if path.suffix.lower() in {".tds", ".tdsx"}:
            item.associated_data_source = path.stem
        if path.name.lower().endswith((".tde.meta.json", "_tde_logic.json", "extract_lineage.json")):
            item.warnings.append("TDE lineage companion metadata detected; used to recover upstream source logic and validation baselines.")
        if path.suffix.lower() == ".tde":
            item.warnings.append("Legacy .tde extract detected. Treat as materialized snapshot/output artifact, not Power BI production source; use only for validation or temporary export fallback.")
        if path.suffix.lower() == ".hyper":
            item.warnings.append("Hyper metadata/preview needs Tableau Hyper API if row-level extract preview is required.")
        if path.suffix.lower() in {".twbx", ".tdsx", ".tflx", ".zip"}:
            item.warnings.append("Package file was inventoried; extracted package contents are listed separately.")
        inventory.append(item)
    return inventory
