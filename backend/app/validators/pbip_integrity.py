from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path

VALID_DATA_SOURCE_VERSION = "powerBI_V3"
VALID_FROM_CARD = {"many", "one"}
VALID_TO_CARD = {"one", "many"}
VALID_CROSS = {"oneDirection", "bothDirections", "automatic"}


def _read_json_no_bom(path: Path, checks: list[dict], blockers: list[str]):
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    checks.append({"check": f"UTF-8 BOM: {path.name}", "status": "Failed" if bom else "Passed", "message": "UTF-8 BOM detected and is not allowed." if bom else "UTF-8 without BOM."})
    if bom: blockers.append(f"{path}: UTF-8 BOM detected")
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
        if node == end: return True
        if node in seen: continue
        seen.add(node); stack.extend(graph.get(node, set()))
    return False


def validate_pbip_tree(pbip_root: Path) -> tuple[list[dict], list[str]]:
    checks: list[dict] = []
    blockers: list[str] = []
    model_files = list(pbip_root.glob("*.SemanticModel/model.bim"))
    report_defs = list(pbip_root.glob("*.Report/definition.pbir"))
    pbip_files = list(pbip_root.glob("*.pbip"))
    if len(model_files) != 1: blockers.append(f"Expected exactly one model.bim, found {len(model_files)}")
    if len(report_defs) != 1: blockers.append(f"Expected exactly one definition.pbir, found {len(report_defs)}")
    if len(pbip_files) != 1: blockers.append(f"Expected exactly one .pbip, found {len(pbip_files)}")
    if blockers: return checks, blockers

    model_doc = _read_json_no_bom(model_files[0], checks, blockers)
    _read_json_no_bom(report_defs[0], checks, blockers)
    _read_json_no_bom(pbip_files[0], checks, blockers)
    if not model_doc: return checks, blockers

    model = model_doc.get("model") or {}
    dsv = model.get("defaultPowerBIDataSourceVersion")
    ok = dsv == VALID_DATA_SOURCE_VERSION
    checks.append({"check":"PowerBIDataSourceVersion","status":"Passed" if ok else "Failed","message":f"defaultPowerBIDataSourceVersion={dsv!r}; expected {VALID_DATA_SOURCE_VERSION!r}."})
    if not ok: blockers.append("Invalid defaultPowerBIDataSourceVersion")

    tables = model.get("tables") or []
    names = [str(t.get("name")) for t in tables]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates: blockers.append("Duplicate semantic tables: " + ", ".join(duplicates))
    checks.append({"check":"Duplicate table detection","status":"Failed" if duplicates else "Passed","message":"No duplicate semantic table names." if not duplicates else str(duplicates)})

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
    checks.append({"check":"Duplicate measure detection","status":"Failed" if duplicate_measures else "Passed","message":"No duplicate measure names across semantic model." if not duplicate_measures else str(sorted(set(duplicate_measures), key=str.casefold))})
    checks.append({"check":"Measure/column collisions","status":"Failed" if object_collisions else "Passed","message":"No measure names collide with columns in the same table." if not object_collisions else str(object_collisions)})

    expressions = {e.get("name"): e for e in model.get("expressions", [])}
    for t in tables:
        for p in t.get("partitions", []):
            expr = str((p.get("source") or {}).get("expression") or "")
            clean = re.sub(r"/\*.*?\*/", "", expr, flags=re.S).strip()
            m_ok = bool(re.search(r"^let\b", clean, flags=re.I)) and bool(re.search(r"\bin\s+[A-Za-z0-9_#\" ]+\s*$", clean, flags=re.I))
            if not m_ok: blockers.append(f"Malformed M query in {t.get('name')}")
            if "SourceFolder" in expr: blockers.append(f"Unnecessary SourceFolder parameter/reference in {t.get('name')}")
            literal_file = re.search(r'File\.Contents\s*\(\s*"', expr, flags=re.I)
            if literal_file: blockers.append(f"Literal File.Contents path detected in {t.get('name')}; source parameter required")
            for ref in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*_SourcePath)\b", expr):
                if ref not in expressions: blockers.append(f"M query {t.get('name')} references missing path parameter {ref}")
    checks.append({"check":"M Query structure/path parameters","status":"Failed" if any("M query" in b or "SourceFolder" in b or "File.Contents" in b for b in blockers) else "Passed","message":"All partitions use let/in structure and parameterized local file paths; no SourceFolder parameter."})

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
        if pair in pair_seen: blockers.append(f"Multiple active relationships between same table pair: {pair}")
        pair_seen.add(pair)
        if r.get("isActive", True):
            if _has_path(graph, str(ft), str(tt)):
                blockers.append(f"Ambiguous/cyclic active relationship path introduced by {r.get('name')}")
            else:
                graph[str(ft)].add(str(tt)); graph[str(tt)].add(str(ft))
    checks.append({"check":"Relationships/cardinality/ambiguity","status":"Failed" if any("Relationship" in b or "relationship" in b or "cyclic" in b for b in blockers) else "Passed","message":"Active relationships reference valid columns, use valid cardinalities, and do not create duplicate/cyclic paths."})
    return checks, blockers
