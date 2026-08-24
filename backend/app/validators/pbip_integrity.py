from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path

VALID_DATA_SOURCE_VERSION = "powerBI_V3"
VALID_FROM_CARD = {"many", "one"}
VALID_TO_CARD = {"one", "many"}
VALID_CROSS = {"oneDirection", "bothDirections", "automatic"}


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json_no_bom(path: Path, checks: list[dict], blockers: list[str]):
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    checks.append({"check": f"UTF-8 BOM: {path.name}", "status": "Failed" if bom else "Passed", "message": "UTF-8 BOM detected and is not allowed." if bom else "UTF-8 without BOM."})
    if bom:
        blockers.append(f"{path}: UTF-8 BOM detected")
    try:
        obj = json.loads(raw.decode("utf-8-sig"))
        checks.append({"check": f"JSON parse: {path.name}", "status": "Passed", "message": "Valid JSON."})
        return obj
    except Exception as exc:
        blockers.append(f"{path}: invalid JSON: {exc}")
        checks.append({"check": f"JSON parse: {path.name}", "status": "Failed", "message": str(exc)})
        return None


def _has_path(graph: dict[str, set[str]], start: str, end: str) -> bool:
    stack, seen = [start], set()
    while stack:
        node = stack.pop()
        if node == end:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.get(node, set()))
    return False


def _strict_excel_m(expr: str) -> str:
    """Remove silent Excel fallbacks from M emitted by older generator versions."""
    if "Excel.Workbook" not in expr:
        return expr

    expr = re.sub(
        r'Workbook_Navigation\s*=\s*try\s+Excel\.Workbook\((.*?)\)\s+otherwise\s+#table\(\{"Name",\s*"Data",\s*"Item",\s*"Kind",\s*"Hidden"\},\s*\{\}\),',
        r'Workbook_Navigation = Excel.Workbook(\1),',
        expr,
        flags=re.S,
    )

    expr = re.sub(
        r'Source_Read\s*=\s*if\s+Table\.RowCount\(Matching_Objects\)\s*>\s*0\s*then\s+Matching_Objects\{0\}\[Data\]\s*else\s+if\s+Table\.RowCount\(Candidate_Objects\)\s*>\s*0\s*then\s+Candidate_Objects\{0\}\[Data\]\s*else\s+#table\(\{\},\s*\{\}\),',
        'Source_Read = if Table.RowCount(Matching_Objects) = 1 then Matching_Objects{0}[Data] '
        'else if Table.RowCount(Matching_Objects) = 0 then error Error.Record("ExcelNavigation", "Requested Excel sheet/table was not found", [RequestedObject = "configured sheet/table"]) '
        'else error Error.Record("ExcelNavigation", "Multiple Excel objects matched the requested sheet/table", [MatchCount = Table.RowCount(Matching_Objects)]),',
        expr,
        flags=re.S,
    )

    # Do not turn a failed source/navigation step into an empty table with no columns.
    expr = re.sub(
        r'Safe_Convert_Values_To_Selected_Types\s*=\s*try\s+Promote_Source_Headers\s+otherwise\s+#table\(\{\},\s*\{\}\),',
        'Safe_Convert_Values_To_Selected_Types = Promote_Source_Headers,',
        expr,
        flags=re.S,
    )
    return expr


def _upgrade_blank_legacy_report(report_dir: Path, checks: list[dict]) -> None:
    """Upgrade the exporter blank PBIR-Legacy skeleton to documented PBIR structure.

    Only blank legacy reports are upgraded. Existing reports that already contain visuals
    are preserved and validated as legacy to avoid destroying migrated content.
    """
    legacy = report_dir / "report.json"
    pbir = report_dir / "definition.pbir"
    if not legacy.exists() or not pbir.exists() or (report_dir / "definition").exists():
        return
    try:
        doc = json.loads(legacy.read_text(encoding="utf-8-sig"))
    except Exception:
        return
    sections = doc.get("sections") or []
    if any((s.get("visualContainers") or []) for s in sections if isinstance(s, dict)):
        return

    page_id = "b8c5fb8d635f898326c6"
    definition = report_dir / "definition"
    _write_json(
        pbir,
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": json.loads(pbir.read_text(encoding="utf-8-sig")).get("datasetReference"),
        },
    )
    _write_json(
        definition / "version.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    _write_json(
        definition / "report.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.2.0/schema.json",
            "themeCollection": {},
            "layoutOptimization": "None",
            "settings": {
                "useStylableVisualContainerHeader": True,
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True,
                "useDefaultAggregateDisplayName": True,
            },
        },
    )
    _write_json(
        definition / "pages" / "pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [page_id],
            "activePageName": page_id,
        },
    )
    _write_json(
        definition / "pages" / page_id / "page.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
            "name": page_id,
            "displayName": "Page 1",
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        },
    )
    legacy.unlink(missing_ok=True)
    checks.append({"check": "PBIR report upgrade", "status": "Passed", "message": "Blank legacy report skeleton upgraded to documented PBIR folder format."})


def _validate_report(report_dir: Path, checks: list[dict], blockers: list[str]) -> None:
    pbir = report_dir / "definition.pbir"
    pbir_doc = _read_json_no_bom(pbir, checks, blockers)
    if not pbir_doc:
        return
    dataset_ref = pbir_doc.get("datasetReference") or {}
    by_path = (dataset_ref.get("byPath") or {}).get("path") if isinstance(dataset_ref, dict) else None
    if not by_path or not str(by_path).startswith("../"):
        blockers.append("Report definition.pbir must reference the local semantic model using a relative byPath reference")

    definition = report_dir / "definition"
    legacy = report_dir / "report.json"
    if definition.exists() and legacy.exists():
        blockers.append("Report contains both PBIR definition/ and PBIR-Legacy report.json; formats are mutually exclusive")
        return

    if definition.exists():
        required = [
            definition / "version.json",
            definition / "report.json",
            definition / "pages" / "pages.json",
        ]
        for path in required:
            if not path.exists():
                blockers.append(f"Missing required PBIR file: {path.relative_to(report_dir)}")
        if any(not p.exists() for p in required):
            return
        version = _read_json_no_bom(required[0], checks, blockers)
        report = _read_json_no_bom(required[1], checks, blockers)
        pages = _read_json_no_bom(required[2], checks, blockers)
        if version and version.get("version") != "2.0.0":
            blockers.append(f"Unsupported PBIR content version: {version.get('version')!r}; expected '2.0.0'")
        if report is not None and "themeCollection" not in report:
            blockers.append("PBIR definition/report.json is missing themeCollection")
        order = (pages or {}).get("pageOrder") or []
        active = (pages or {}).get("activePageName")
        if not order:
            blockers.append("PBIR report contains no pages")
        if active not in order:
            blockers.append("PBIR activePageName is not present in pageOrder")
        for page_id in order:
            page_path = definition / "pages" / str(page_id) / "page.json"
            if not page_path.exists():
                blockers.append(f"Missing PBIR page definition for {page_id}")
                continue
            page = _read_json_no_bom(page_path, checks, blockers)
            if page and (page.get("name") != page_id or not page.get("displayName")):
                blockers.append(f"Invalid PBIR page metadata for {page_id}")
        checks.append({"check": "PBIR report structure", "status": "Failed" if any("PBIR" in b for b in blockers) else "Passed", "message": "Enhanced report definition, page order and page metadata validated."})
    elif legacy.exists():
        legacy_doc = _read_json_no_bom(legacy, checks, blockers)
        sections = (legacy_doc or {}).get("sections") or []
        if not sections:
            blockers.append("PBIR-Legacy report.json contains no report sections/pages")
        checks.append({"check": "PBIR-Legacy report structure", "status": "Failed" if not sections else "Passed", "message": "Legacy report page collection validated."})
    else:
        blockers.append("Report folder has neither PBIR definition/ nor PBIR-Legacy report.json")


def validate_pbip_tree(pbip_root: Path) -> tuple[list[dict], list[str]]:
    checks: list[dict] = []
    blockers: list[str] = []
    model_files = list(pbip_root.glob("*.SemanticModel/model.bim"))
    report_defs = list(pbip_root.glob("*.Report/definition.pbir"))
    pbip_files = list(pbip_root.glob("*.pbip"))
    if len(model_files) != 1:
        blockers.append(f"Expected exactly one model.bim, found {len(model_files)}")
    if len(report_defs) != 1:
        blockers.append(f"Expected exactly one definition.pbir, found {len(report_defs)}")
    if len(pbip_files) != 1:
        blockers.append(f"Expected exactly one .pbip, found {len(pbip_files)}")
    if blockers:
        return checks, blockers

    report_dir = report_defs[0].parent
    _upgrade_blank_legacy_report(report_dir, checks)

    model_doc = _read_json_no_bom(model_files[0], checks, blockers)
    _read_json_no_bom(pbip_files[0], checks, blockers)
    _validate_report(report_dir, checks, blockers)
    if not model_doc:
        return checks, blockers

    model = model_doc.get("model") or {}
    dsv = model.get("defaultPowerBIDataSourceVersion")
    ok = dsv == VALID_DATA_SOURCE_VERSION
    checks.append({"check": "PowerBIDataSourceVersion", "status": "Passed" if ok else "Failed", "message": f"defaultPowerBIDataSourceVersion={dsv!r}; expected {VALID_DATA_SOURCE_VERSION!r}."})
    if not ok:
        blockers.append("Invalid defaultPowerBIDataSourceVersion")

    tables = model.get("tables") or []
    names = [str(t.get("name")) for t in tables]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        blockers.append("Duplicate semantic tables: " + ", ".join(duplicates))
    checks.append({"check": "Duplicate table detection", "status": "Failed" if duplicates else "Passed", "message": "No duplicate semantic table names." if not duplicates else str(duplicates)})

    table_cols = {t.get("name"): {c.get("name") for c in t.get("columns", [])} for t in tables}
    global_measures: dict[str, str] = {}
    duplicate_measures: list[str] = []
    object_collisions: list[str] = []
    for t in tables:
        col_names = {str(c.get("name") or "").casefold() for c in t.get("columns", [])}
        for m in t.get("measures", []) or []:
            mname = str(m.get("name") or "").strip()
            key = mname.casefold()
            if not key:
                continue
            if key in global_measures:
                duplicate_measures.append(mname)
            else:
                global_measures[key] = str(t.get("name") or "")
            if key in col_names:
                object_collisions.append(f"{t.get('name')}[{mname}]")
    if duplicate_measures:
        blockers.append("Duplicate measures: " + ", ".join(sorted(set(duplicate_measures), key=str.casefold)))
    if object_collisions:
        blockers.append("Measure/column name collisions: " + ", ".join(object_collisions))
    checks.append({"check": "Duplicate measure detection", "status": "Failed" if duplicate_measures else "Passed", "message": "No duplicate measure names across semantic model." if not duplicate_measures else str(sorted(set(duplicate_measures), key=str.casefold))})
    checks.append({"check": "Measure/column collisions", "status": "Failed" if object_collisions else "Passed", "message": "No measure names collide with columns in the same table." if not object_collisions else str(object_collisions)})

    expressions = {e.get("name"): e for e in model.get("expressions", [])}
    model_changed = False
    for t in tables:
        for p in t.get("partitions", []):
            source = p.get("source") or {}
            expr = str(source.get("expression") or "")
            strict = _strict_excel_m(expr)
            if strict != expr:
                source["expression"] = strict
                expr = strict
                model_changed = True
            clean = re.sub(r"/\*.*?\*/", "", expr, flags=re.S).strip()
            m_ok = bool(re.search(r"^let\b", clean, flags=re.I)) and bool(re.search(r"\bin\s+[A-Za-z0-9_#\" ]+\s*$", clean, flags=re.I))
            if not m_ok:
                blockers.append(f"Malformed M query in {t.get('name')}")
            if "SourceFolder" in expr:
                blockers.append(f"Unnecessary SourceFolder parameter/reference in {t.get('name')}")
            if re.search(r'File\.Contents\s*\(\s*"', expr, flags=re.I):
                blockers.append(f"Literal File.Contents path detected in {t.get('name')}; source parameter required")
            if any(token in expr for token in ('"<server>"', '"<database>"', '"<table>"', '"<schema>"')):
                blockers.append(f"Unresolved database source identity placeholder in {t.get('name')}")
            for ref in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*_SourcePath)\b", expr):
                if ref not in expressions:
                    blockers.append(f"M query {t.get('name')} references missing path parameter {ref}")

    # Block cloud runtime paths leaking into a client PBIP parameter.
    for name, exp in expressions.items():
        value = str(exp.get("expression") or "")
        if re.search(r'"/(tmp|var/tmp)/', value):
            blockers.append(f"Path parameter {name} contains a cloud runtime path that cannot refresh on the client")

    if model_changed:
        _write_json(model_files[0], model_doc)
        checks.append({"check": "Excel navigation hardening", "status": "Passed", "message": "Removed silent empty-table and first-sheet fallbacks from generated Excel M queries."})

    checks.append({"check": "M Query structure/path parameters", "status": "Failed" if any("M query" in b or "SourceFolder" in b or "File.Contents" in b or "placeholder" in b or "cloud runtime" in b for b in blockers) else "Passed", "message": "Partitions use let/in structure, strict Excel navigation, valid database identity and parameterized local file paths."})

    graph: dict[str, set[str]] = defaultdict(set)
    pair_seen = set()
    for r in model.get("relationships", []):
        ft, fc, tt, tc = r.get("fromTable"), r.get("fromColumn"), r.get("toTable"), r.get("toColumn")
        if ft not in table_cols or fc not in table_cols.get(ft, set()) or tt not in table_cols or tc not in table_cols.get(tt, set()):
            blockers.append(f"Relationship references missing table/column: {r.get('name')}")
        if r.get("fromCardinality") not in VALID_FROM_CARD or r.get("toCardinality") not in VALID_TO_CARD:
            blockers.append(f"Invalid relationship cardinality: {r.get('name')}")
        if r.get("crossFilteringBehavior") not in VALID_CROSS:
            blockers.append(f"Invalid cross-filter behavior: {r.get('name')}")
        pair = tuple(sorted((str(ft), str(tt))))
        if pair in pair_seen:
            blockers.append(f"Multiple active relationships between same table pair: {pair}")
        pair_seen.add(pair)
        if r.get("isActive", True):
            if _has_path(graph, str(ft), str(tt)):
                blockers.append(f"Ambiguous/cyclic active relationship path introduced by {r.get('name')}")
            else:
                graph[str(ft)].add(str(tt))
                graph[str(tt)].add(str(ft))
    checks.append({"check": "Relationships/cardinality/ambiguity", "status": "Failed" if any("Relationship" in b or "relationship" in b or "cyclic" in b for b in blockers) else "Passed", "message": "Active relationships reference valid columns, use valid cardinalities, and do not create duplicate/cyclic paths."})
    return checks, blockers
