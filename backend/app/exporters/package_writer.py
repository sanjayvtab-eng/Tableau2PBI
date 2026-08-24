from __future__ import annotations
import csv
import hashlib
import shutil
import zipfile
from pathlib import Path
from app.core.json_utils import write_json
from app.core.name_sanitizer import clean_name
from app.models.schemas import MigrationProject
from app.validators.pbip_integrity import validate_pbip_tree


def _safe_file_stem(value: str | None, fallback: str = "Object", max_len: int = 72) -> str:
    cleaned = clean_name(value or fallback, fallback=fallback).replace(" ", "_")
    if len(cleaned) <= max_len:
        return cleaned
    digest = hashlib.sha1(cleaned.encode("utf-8", errors="ignore")).hexdigest()[:8]
    # Keep the final value inside max_len, including the separator + digest.
    prefix_len = max(1, max_len - len(digest) - 1)
    return f"{cleaned[:prefix_len]}_{digest}"


def _short_export_id(project: MigrationProject) -> str:
    """Stable, Windows-safe PBIP identifier deliberately independent of the workbook name."""
    raw = str(getattr(project, "project_id", "") or getattr(project, "project_name", "") or "project")
    token = "".join(ch for ch in raw if ch.isalnum()).upper()
    if len(token) < 8:
        token = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest().upper()
    return f"P{token[:8]}"


def _portable_pbip_paths(export_id: str) -> dict[str, Path]:
    """Return the intentionally shallow PBIP layout used inside the download ZIP."""
    root = Path("PBI")
    return {
        "root": root,
        "pbip": root / f"{export_id}.pbip",
        "semantic": root / f"{export_id}.SemanticModel",
        "report": root / f"{export_id}.Report",
        # Power BI may create/read this file even when it is not emitted by us.
        "deepest_expected": root / f"{export_id}.SemanticModel" / ".pbi" / "editorSettings.json",
    }


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys or ["message"])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k)) for k in keys})


def _csv_value(value):
    if isinstance(value, (dict, list)):
        import json
        return json.dumps(value, ensure_ascii=False)
    return value


def _flatten_tde_rows(project: MigrationProject) -> list[dict]:
    rows = []
    for t in getattr(project, "tde_analysis", []) or []:
        for f in t.get("tde_files", []) or [{"file_name": t.get("tde_file")}]:
            rows.append({
                "tde_file": f.get("file_name") or t.get("tde_file"),
                "folder_path": f.get("folder_path"),
                "scenario": t.get("scenario"),
                "is_source_of_truth": t.get("is_source_of_truth"),
                "recommended_usage": t.get("recommended_usage"),
                "decision": t.get("decision"),
                "preferred_architecture": t.get("preferred_architecture"),
                "temporary_fallback": t.get("temporary_fallback"),
                "metadata_files_found": t.get("metadata_files_found"),
                "original_sources_detected": t.get("original_sources_detected"),
                "custom_sql_detected": bool(t.get("custom_sql_detected")),
                "multiple_upstream_sources_detected": t.get("multiple_upstream_sources_detected"),
            })
    return rows


def _tde_manual_review_rows(project: MigrationProject) -> list[dict]:
    rows = []
    for t in getattr(project, "tde_analysis", []) or []:
        for item in t.get("manual_review_required", []) or []:
            rows.append({
                "tde_file": t.get("tde_file"),
                "manual_review_item": item,
                "reason": "TDE migration must not silently convert uncertain Tableau behavior.",
                "recommended_action": "Validate with source owner and Tableau output before applying in Power BI.",
            })
        for filt in t.get("extract_filter_classification", []) or []:
            if str(filt.get("purpose", "")).startswith("Unknown"):
                rows.append({
                    "tde_file": t.get("tde_file"),
                    "manual_review_item": "Unknown extract filter purpose",
                    "object": filt.get("filter"),
                    "reason": filt.get("reason"),
                    "recommended_action": filt.get("powerbi_target"),
                })
    return rows


def _tde_column_validation_rows(project: MigrationProject) -> list[dict]:
    rows = []
    for t in getattr(project, "tde_analysis", []) or []:
        for v in t.get("source_column_validation", []) or []:
            rows.append({
                "tde_file": t.get("tde_file"),
                "source_name": v.get("source_name"),
                "source_id": v.get("source_id"),
                "target_connector": v.get("target_connector"),
                "source_path_or_table": v.get("source_path_or_table"),
                "preview_available": v.get("preview_available"),
                "source_column_count": v.get("source_column_count"),
                "source_columns": v.get("source_columns"),
                "matched_tableau_columns": v.get("matched_tableau_columns"),
                "missing_tableau_fields_for_review": v.get("missing_tableau_fields_for_review"),
                "status": v.get("status"),
                "warnings": v.get("warnings"),
            })
    return rows


def _tde_rebuild_plan(project: MigrationProject) -> str:
    lines = [
        "# TDE Rebuild Plan",
        "",
        "A Tableau .tde extract is treated as a legacy output artifact and validation baseline, not as the Power BI source of truth.",
        "The default architecture is: Original source systems -> reusable transformation layer -> Power BI semantic model -> DAX measures -> reports.",
        "",
    ]
    if not getattr(project, "tde_analysis", []):
        lines.append("No .tde extract was detected in this project.")
        return "\n".join(lines)
    for t in project.tde_analysis:
        lines.extend([
            f"## {t.get('tde_file')}",
            f"- Scenario: {t.get('scenario')}",
            f"- Decision: {t.get('decision')}",
            f"- Preferred architecture: {t.get('preferred_architecture')}",
            f"- Temporary fallback: {t.get('temporary_fallback')}",
            "",
            "### Recovered sources",
        ])
        recovered_sources = t.get("recovered_sources") or []
        if recovered_sources:
            for s in recovered_sources:
                lines.append(f"- {s.get('source_name') or s.get('name')}: {s.get('source_type') or s.get('recommended_powerbi_connector') or 'Unknown'} -> {s.get('migration_target') or 'Power Query/Dataflow/SQL staging'}")
        else:
            lines.append("- No original source was deterministically recovered. Ask for TWB/TDS/TFL metadata or source-owner details before production migration.")
        lines.extend(["", "### Recovered logic flags"])
        for k, v in (t.get("recovered_logic") or {}).items():
            lines.append(f"- {k}: {v}")
        lines.extend(["", "### Validation baseline checkpoints"])
        for v in t.get("validation_checkpoints") or []:
            lines.append(f"- {v}")
        lines.extend(["", "### Do not migrate blindly"])
        for v in t.get("omit_rules") or []:
            lines.append(f"- {v}")
        lines.append("")
    return "\n".join(lines)


def _application_capability_guide() -> str:
    return """# TABLEAU2PBI Input Package Guide

## Recommended ZIP contents
Include as many of these as available:
- Tableau workbook: .twb or .twbx
- Tableau data source: .tds or .tdsx
- Tableau Prep flow: .tfl or .tflx
- Local source files: .csv, .xlsx/.xls, .txt, .json, .xml, .parquet
- SQL scripts or view definitions used by Tableau
- Extracts: .hyper and/or legacy .tde
- TDE metadata companion file if available: *.tde.meta.json or extract_lineage.json
- Images/backgrounds/custom shapes used by dashboards
- Optional validation baselines: row counts, totals, screenshots, Tableau summary exports

## What the application can do
- Inventory the full package and nested TWBX/TDSX/TFLX contents.
- Parse Tableau XML metadata from workbook/data-source/prep files.
- Detect data sources, joins, relationships, unions, filters, calculated fields, parameters, dashboards, sheets, and visual encodings.
- Detect TDE usage, recover likely source logic from Tableau metadata, and ignore TDE as production source when original sources are present.
- Generate source mapping, previews, datatype profiling, M review files, DAX review files, semantic-model metadata, visual build plan, validation report, and migration report.

## What the application cannot guarantee automatically
- Perfect Tableau-to-Power BI visual pixel layout.
- Business validation of every metric without source-owner sign-off.
- Exact automatic conversion of complex table calculations, external scripts/model extensions, ambiguous LOD context, credentials, or unknown extract-filter intent.
- Recovery of original upstream logic from a standalone .tde file with no Tableau metadata.

## TDE rule
Do not design Power BI as Tableau TDE -> Power BI. Recover original sources and transformation logic where possible. Use TDE only as validation baseline or temporary static fallback.
"""


def _migration_report(project: MigrationProject) -> str:
    lines = [
        f"# Tableau to Power BI Migration Report - {project.project_name}",
        "",
        f"Health status: **{project.health_status}**",
        "",
        "## Executive Guidance",
        "This workbench migrates business logic, not Tableau mechanics. Safe Openable Mode keeps unsupported/ambiguous logic in lineage and manual-review artifacts instead of writing invalid Power BI objects.",
        "",
        "## Summary",
    ]
    for k, v in project.summary.items():
        lines.append(f"- {k}: {v}")
    lines.extend(["", "## Recommended ZIP Contents and Tool Scope", _application_capability_guide(), "", "## File Inventory"])
    for item in project.inventory:
        status = item.parsed_status
        warnings = f" | warnings: {'; '.join(item.warnings)}" if item.warnings else ""
        errors = f" | errors: {'; '.join(item.errors)}" if item.errors else ""
        lines.append(f"- {item.folder_path}/{item.file_name} ({item.role}) - {status}{warnings}{errors}")
    lines.extend(["", "## Data Sources"])
    for ds in project.datasources:
        lines.append(f"- {ds.name}: {len(ds.connections)} connection(s), {len(ds.fields)} field(s), {len(ds.relations)} relation(s), {len(ds.filters)} filter(s)")
    lines.extend(["", "## Source Mappings"])
    for m in project.source_mappings:
        lines.append(f"- {m.datasource}: {m.target_connector} | path={m.target_file_path or m.detected_source_path or 'N/A'} | table={m.table_name or 'N/A'} | status={m.mapping_status}")
    lines.extend(["", "## TDE Extract Analysis and Migration Strategy"])
    if not getattr(project, "tde_analysis", []):
        lines.append("No legacy Tableau .tde extracts detected.")
    for tde in getattr(project, "tde_analysis", []):
        lines.extend([
            f"### {tde.get('tde_file')}",
            f"- Scenario: {tde.get('scenario')}",
            f"- TDE role: {tde.get('tde_role')}",
            f"- Source of truth: {tde.get('is_source_of_truth')}",
            f"- Recommended usage: {tde.get('recommended_usage')}",
            f"- Decision: {tde.get('decision')}",
            f"- Preferred architecture: {tde.get('preferred_architecture')}",
            f"- Temporary fallback: {tde.get('temporary_fallback')}",
            "",
            "Recovered sources:",
        ])
        for s in tde.get("recovered_sources") or []:
            lines.append(f"- {s.get('source_name') or s.get('name')}: {s.get('source_type') or s.get('recommended_powerbi_connector') or 'Unknown'}")
        lines.append("Recovered logic flags:")
        for k, v in (tde.get("recovered_logic") or {}).items():
            lines.append(f"- {k}: {v}")
        lines.append("Extract filter classification:")
        for f in tde.get("extract_filter_classification") or []:
            lines.append(f"- {f.get('purpose')}: {f.get('powerbi_target')} | {f.get('reason')}")
    lines.extend(["", "## Visual Conversion Plan"])
    for v in project.visual_plan:
        lines.append(f"- {v.get('worksheet')}: Tableau mark {v.get('tableau_marks_type')} -> {v.get('recommended_powerbi_visual')} | fields={v.get('fields_used')}")
    lines.extend(["", "## Calculation Conversion"])
    for c in project.calculations:
        lines.append(f"- {c.name}: {c.target_object_type}, confidence {c.confidence_score}, used in {', '.join(c.used_in) if c.used_in else 'N/A'}")
        lines.append(f"  - Tableau formula: {c.formula}")
        if c.generated_expression:
            lines.append(f"  - Generated expression: {c.generated_expression}")
        if c.manual_review_notes:
            lines.append(f"  - Manual review: {'; '.join(c.manual_review_notes)}")
    lines.extend(["", "## Migration Strategy Decisions"])
    if not project.migration_decisions:
        lines.append("No migration strategy decisions were generated.")
    for d in project.migration_decisions[:500]:
        flag = "MANUAL REVIEW" if d.get("manual_review") else "AUTO/SAFE"
        lines.append(f"- [{flag}] {d.get('category')} / {d.get('object_name')}: {d.get('powerbi_target')} - {d.get('migration_decision')}")
    lines.extend(["", "## Reconciliation Plan"])
    for step in project.reconciliation_plan:
        lines.append(f"- Step {step.get('step')}: {step.get('checkpoint')} - {step.get('validation')}")
    lines.extend(["", "## Validation Issues"])
    if not project.validation_issues:
        lines.append("No validation issues detected.")
    for issue in project.validation_issues:
        lines.append(f"- [{issue.severity.upper()}] {issue.category} / {issue.object_name}: {issue.message}")
        if issue.recommended_fix:
            lines.append(f"  - Recommended fix: {issue.recommended_fix}")
    lines.append("\n## Safe Openable Mode\nUnsupported Tableau logic is preserved in lineage/review files and not forced into invalid Power BI objects.")
    return "\n".join(lines)


def _tabular_type(value: str | None) -> str:
    v = str(value or "Text").strip().lower().replace(" ", "")
    return {
        "text": "string", "string": "string", "varchar": "string", "char": "string",
        "wholenumber": "int64", "integer": "int64", "int": "int64", "int64": "int64",
        "decimalnumber": "double", "real": "double", "float": "double", "number": "double", "double": "double",
        "fixeddecimal/currency": "decimal", "currency": "decimal", "decimal": "decimal",
        "date": "dateTime", "datetime": "dateTime", "timestamp": "dateTime", "time": "dateTime",
        "true/false": "boolean", "boolean": "boolean", "bool": "boolean", "binary": "binary",
        "any": "string",
    }.get(v, "string")


def _relationship_json(r) -> dict:
    card = (r.cardinality or "Many-to-one").lower()
    if card == "one-to-one":
        from_card, to_card = "one", "one"
    elif card == "one-to-many":
        from_card, to_card = "one", "many"
    elif card == "many-to-many":
        from_card, to_card = "many", "many"
    else:
        from_card, to_card = "many", "one"
    cross = "bothDirections" if str(r.cross_filter_direction).lower().startswith("both") else "oneDirection"
    return {
        "name": clean_name(r.id or f"{r.from_table}_{r.to_table}"),
        "fromTable": r.from_table,
        "fromColumn": r.from_column,
        "toTable": r.to_table,
        "toColumn": r.to_column,
        "fromCardinality": from_card,
        "toCardinality": to_card,
        "crossFilteringBehavior": cross,
        "isActive": bool(r.active),
    }


def _safe_dax_expression(expression: str) -> bool:
    """Conservative Safe-Openable-mode guard for generated DAX.

    This is intentionally not a full DAX parser.  It blocks known Tableau syntax and
    known translator patterns that Power BI cannot deserialize/compile safely.
    Unsupported expressions stay in migration review artifacts instead of model.bim.
    """
    import re
    expr = str(expression or "").strip()
    if not expr:
        return False
    upper = expr.upper()
    banned = (
        "ELSEIF", " THEN ", " END", "ZN(", "DATETRUNC(", "DATEPARSE(",
        "RUNNING_SUM(", "RUNNING_AVG(", "RUNNING_COUNT(", "RUNNING_MIN(",
        "RUNNING_MAX(", "WINDOW_", "RANK_DENSE(", "RANK_UNIQUE(",
        "RANK_MODIFIED(", "PREVIOUS_VALUE(", "LOOKUP(", "ATTR(",
    )
    if any(token in upper for token in banned):
        return False
    # Tableau DATEDIFF('day', start, end) is not DAX DATEDIFF(start,end,DAY).
    if re.search(r"DATEDIFF\s*\(\s*['\"](?:day|week|month|quarter|year|hour|minute|second)['\"]\s*,", expr, re.I):
        return False
    # Tableau CONTAINS(string, substring) is not the DAX CONTAINS(table, ...).
    if re.search(r"\bCONTAINS\s*\(\s*'[^']+'\s*\[", expr, re.I):
        return False
    return True


def _dedupe_model_objects(columns: list[dict], measures: list[dict]) -> tuple[list[dict], list[dict]]:
    """Power BI table object names are treated case-insensitively for safe export.

    Preserve the first canonical column/measure and drop duplicate names.  Also avoid
    measure/column name collisions, which can produce 'Item already exists in the
    collection' during model.bim deserialization.
    """
    clean_columns: list[dict] = []
    clean_measures: list[dict] = []
    used: set[str] = set()
    for c in columns:
        name = str(c.get("name") or "").strip()
        key = name.casefold()
        if not name or key in used:
            continue
        used.add(key)
        clean_columns.append(c)
    for m in measures:
        name = str(m.get("name") or "").strip()
        key = name.casefold()
        if not name or key in used:
            continue
        used.add(key)
        clean_measures.append(m)
    return clean_columns, clean_measures



def _prepare_export_semantic_tables(project: MigrationProject) -> list:
    """Return export-only semantic tables with parsed Tableau calculations attached.

    The upstream parser already stores calculations in ``project.calculations`` while
    semantic tables may legitimately arrive without populated ``measures``/calculated
    columns.  PBIP export must bridge that gap without changing the source project.
    Only high-confidence, safe DAX is promoted; unsupported logic remains in the
    existing review/DAX artifacts.
    """
    import copy
    import re

    tables = copy.deepcopy(list(project.semantic_tables or []))
    if not tables:
        return tables

    mappings_by_source = {str(m.source_id): m for m in project.source_mappings}
    table_by_name = {str(t.name).casefold(): t for t in tables if getattr(t, "name", None)}

    def _table_candidates(calc):
        expression = str(getattr(calc, "generated_expression", "") or "")
        refs = re.findall(r"'([^']+)'\[([^\]]+)\]", expression)

        # 1) Prefer an explicit table reference already produced by the DAX translator.
        explicit = []
        for table_name, _column in refs:
            t = table_by_name.get(table_name.casefold())
            if t and t not in explicit:
                explicit.append(t)
        if explicit:
            print(f"[{calc.name}] returned explicit: {[e.name for e in explicit]}")
            return explicit

        # 2) Score tables by referenced column ownership and datasource mapping.
        referenced_columns = [c.casefold() for _tbl, c in refs]
        if not referenced_columns:
            referenced_columns = [
                c.casefold()
                for c in re.findall(r"\[([^\]]+)\]", expression)
            ]

        calc_datasource = str(getattr(calc, "datasource", "") or "").casefold()
        scored = []
        for t in tables:
            score = 0
            column_names = {
                str(c.get("name") or "").casefold()
                for c in (getattr(t, "columns", None) or [])
                if isinstance(c, dict)
            }
            score += sum(2 for c in referenced_columns if c in column_names)

            mapping = mappings_by_source.get(str(getattr(t, "source_id", "") or ""))
            if mapping:
                if str(getattr(mapping, "datasource", "") or "").casefold() == calc_datasource:
                    score += 3
                if str(getattr(mapping, "table_name", "") or "").casefold() == str(getattr(t, "name", "") or "").casefold():
                    score += 2

            if score:
                scored.append((score, t))

        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            return [scored[0][1]]

        # 3) If there is exactly one export table, it is an unambiguous target.
        if len(tables) == 1:
            return tables

        return []

    def _ensure_unique_column(table, item):
        existing = {
            str(c.get("name") or "").casefold()
            for c in (getattr(table, "columns", None) or [])
            if isinstance(c, dict)
        }
        if item["name"].casefold() not in existing:
            table.columns.append(item)

    def _ensure_unique_measure(table, item):
        existing = {
            str(m.get("name") or "").casefold()
            for m in (getattr(table, "measures", None) or [])
            if isinstance(m, dict)
        }
        if item["name"].casefold() not in existing:
            table.measures.append(item)

    for calc in project.calculations or []:
        expression = str(getattr(calc, "generated_expression", "") or "").strip()
        if not expression or getattr(calc, "confidence_score", 0) < 0.70:
            continue
        if not _safe_dax_expression(expression):
            continue

        target_type = str(getattr(calc, "target_object_type", "") or "").strip().casefold()
        name = clean_name(str(getattr(calc, "name", "") or "").strip())
        if not name:
            continue

        candidates = _table_candidates(calc)
        if not candidates:
            continue
        table = candidates[0]

        if target_type in {"measure", "calculated measure"}:
            _ensure_unique_measure(table, {
                "name": name,
                "expression": expression,
                "description": getattr(calc, "description", None),
            })
        elif target_type in {"calculated_column", "calculated column", "column"}:
            data_type = (
                getattr(calc, "data_type", None)
                or getattr(calc, "datatype", None)
                or "Text"
            )
            _ensure_unique_column(table, {
                "name": name,
                "source_name": name,
                "data_type": data_type,
                "calculated": True,
                "expression": expression,
            })

    # Diagnostic logging requested by user
    import logging
    for t in tables:
        logging.info(f"SEMANTIC TABLE: {t.name} | MEASURES ATTACHED: {len(getattr(t, 'measures', []) or [])}")

    return tables

def _model_bim(project: MigrationProject, semantic_tables: list | None = None) -> dict:
    import json
    import re
    import uuid
    mapping_by_source = {m.source_id: m for m in project.source_mappings}
    tables = []
    expressions = []
    expression_names = set()
    global_measure_names: set[str] = set()
    export_tables = semantic_tables if semantic_tables is not None else project.semantic_tables

    for t in export_tables:
        if not t.include_in_export:
            continue
        cols = []
        for c in t.columns:
            item = {"name": c.get("name"), "dataType": _tabular_type(c.get("data_type")), "lineageTag": str(uuid.uuid4())}
            if c.get("calculated") and c.get("expression"):
                # Safe Openable Mode: never inject known Tableau-only/invalid DAX.
                if not _safe_dax_expression(c.get("expression")):
                    continue
                item["type"] = "calculated"
                item["expression"] = c.get("expression")
            else:
                item["sourceColumn"] = c.get("source_name") or c.get("name")
                item["summarizeBy"] = "none"
            cols.append(item)
        measures = []
        for m in t.measures:
            if not m.get("name") or not m.get("expression") or not _safe_dax_expression(m.get("expression")):
                continue
            measure_name = clean_name(str(m.get("name")))
            measure_key = measure_name.casefold()
            # Belt-and-suspenders protection: measure names are canonical across the
            # exported model. Upstream duplicate signals are never written twice.
            if measure_key in global_measure_names:
                continue
            measure = {"name": measure_name, "expression": m.get("expression"), "lineageTag": str(uuid.uuid4())}
            if m.get("description"):
                measure["description"] = m.get("description")
            measures.append(measure)
            global_measure_names.add(measure_key)
        cols, measures = _dedupe_model_objects(cols, measures)
        table = {
            "name": t.name,
            "lineageTag": str(uuid.uuid4()),
            "columns": cols,
            "partitions": [{"name": f"{t.name} Partition", "mode": "import", "source": {"type": "m", "expression": t.m_query or "let\n    Source = #table({}, {})\nin\n    Source"}}],
        }
        if measures:
            table["measures"] = measures
        tables.append(table)

        mapping = mapping_by_source.get(t.source_id)
        if mapping and mapping.powerbi_path_parameter and mapping.resolved_powerbi_path:
            pname = mapping.powerbi_path_parameter
            if pname not in expression_names:
                expressions.append({
                    "name": pname,
                    "kind": "m",
                    "expression": json.dumps(mapping.resolved_powerbi_path, ensure_ascii=False),
                    "annotations": [
                        {"name": "IsParameterQuery", "value": "True"},
                        {"name": "Type", "value": "Text"},
                        {"name": "IsParameterQueryRequired", "value": "True"},
                    ],
                })
                expression_names.add(pname)

    valid_table_cols = {t["name"]: {c["name"] for c in t.get("columns", [])} for t in tables}
    relationships = []
    for r in project.relationships:
        if not r.active or r.manual_review:
            continue
        if r.from_table not in valid_table_cols or r.to_table not in valid_table_cols:
            continue
        if r.from_column not in valid_table_cols[r.from_table] or r.to_column not in valid_table_cols[r.to_table]:
            continue
        if (r.cardinality or "").lower() == "many-to-many":
            continue
        relationships.append(_relationship_json(r))

    model = {
        "culture": "en-US",
        "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "tables": tables,
        "relationships": relationships,
    }
    if expressions:
        model["expressions"] = expressions
    return {"compatibilityLevel": 1601, "model": model}


class ExportValidationError(RuntimeError):
    """Raised when export pre-validation finds a blocking problem."""


class _ExportSession:
    def __init__(self, project: MigrationProject, staging_root: Path, final_root: Path, final_zip: Path):
        import datetime as _dt
        self.project = project
        self.staging_root = staging_root
        self.final_root = final_root
        self.final_zip = final_zip
        self.started_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
        self.records: list[dict] = []
        self.warnings: list[str] = []
        self.manual_actions: list[str] = []
        self.prevalidation: list[dict] = []

    def record(self, path: Path, status: str, message: str = "", size_bytes: int | None = None) -> None:
        try:
            relative = str(path.relative_to(self.staging_root)).replace("\\", "/")
        except ValueError:
            relative = str(path)
        self.records.append({
            "path": relative,
            "status": status,
            "message": message,
            "size_bytes": size_bytes,
        })

    def write_text(self, relative: str | Path, content: str) -> Path:
        path = self.staging_root / relative
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content or "", encoding="utf-8")
            self.record(path, "Success", size_bytes=path.stat().st_size)
            return path
        except Exception as exc:
            self.record(path, "Error", str(exc))
            raise

    def write_json(self, relative: str | Path, payload) -> Path:
        import json
        return self.write_text(relative, json.dumps(payload, indent=2, default=str, ensure_ascii=False))

    def write_csv(self, relative: str | Path, rows: list[dict]) -> Path:
        import io
        keys: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=keys or ["message"])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k)) for k in keys})
        return self.write_text(relative, buffer.getvalue())

    def skip(self, relative: str | Path, message: str) -> None:
        self.record(self.staging_root / relative, "Skipped", message)

    def log_payload(self, status: str) -> dict:
        import datetime as _dt
        return {
            "application": "TABLEAU2PBI Enterprise Migration Workbench",
            "export_engine_version": "11.6.5",
            "project_id": self.project.project_id,
            "project_name": self.project.project_name,
            "status": status,
            "started_at_utc": self.started_at,
            "completed_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "final_folder": str(self.final_root),
            "final_zip": str(self.final_zip),
            "prevalidation": self.prevalidation,
            "summary": {
                "success": sum(1 for r in self.records if r["status"] == "Success"),
                "skipped": sum(1 for r in self.records if r["status"] == "Skipped"),
                "errors": sum(1 for r in self.records if r["status"] == "Error"),
                "warnings": len(self.warnings),
                "manual_actions": len(self.manual_actions),
            },
            "warnings": self.warnings,
            "manual_actions_required": self.manual_actions,
            "files": self.records,
        }

    def write_logs(self, status: str = "Success") -> None:
        import html
        payload = self.log_payload(status)
        # Write JSON directly so it is included in its own file list only after creation.
        self.write_json("ExportLog.json", payload)
        rows = []
        for r in self.records:
            rows.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html.escape(r["status"]), html.escape(r["path"]),
                    html.escape(str(r.get("size_bytes") or "")), html.escape(r.get("message") or "")
                )
            )
        checks = "".join(
            f"<li><strong>{html.escape(c['status'])}</strong> — {html.escape(c['check'])}: {html.escape(c['message'])}</li>"
            for c in self.prevalidation
        )
        warnings = "".join(f"<li>{html.escape(x)}</li>" for x in self.warnings) or "<li>None</li>"
        actions = "".join(f"<li>{html.escape(x)}</li>" for x in self.manual_actions) or "<li>None</li>"
        page = f"""<!doctype html><html><head><meta charset='utf-8'><title>TABLEAU2PBI Export Log</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:32px;color:#182033}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d8deea;padding:8px;text-align:left;vertical-align:top}}th{{background:#eef2ff}}.ok{{color:#166534}}.warn{{color:#92400e}}</style></head><body>
<h1>TABLEAU2PBI Export Log</h1><p><strong>Project:</strong> {html.escape(self.project.project_name)}</p><p><strong>Status:</strong> {html.escape(status)}</p>
<h2>Pre-validation</h2><ul>{checks}</ul><h2>Warnings</h2><ul>{warnings}</ul><h2>Manual actions required</h2><ul>{actions}</ul>
<h2>Generated artifacts</h2><table><thead><tr><th>Status</th><th>File</th><th>Bytes</th><th>Message</th></tr></thead><tbody>{''.join(rows)}</tbody></table></body></html>"""
        self.write_text("ExportLog.html", page)


def _export_prevalidate(project: MigrationProject, workspace: Path, exports_dir: Path, final_root: Path) -> list[dict]:
    checks: list[dict] = []
    blockers: list[str] = []

    def add(check: str, ok: bool, message: str, warning: bool = False) -> None:
        status = "Warning" if ok and warning else ("Passed" if ok else "Failed")
        checks.append({"check": check, "status": status, "message": message})
        if not ok:
            blockers.append(f"{check}: {message}")

    add("Workspace path", workspace.exists() and workspace.is_dir(), str(workspace))
    try:
        exports_dir.mkdir(parents=True, exist_ok=True)
        probe = exports_dir / f".write_test_{project.project_id}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        add("Workspace write permission", True, f"Writable: {exports_dir}")
    except Exception as exc:
        add("Workspace write permission", False, str(exc))

    add("Project name", bool((project.project_name or "").strip()), "Project name is available." if project.project_name else "Project name is empty.")
    add("Project metadata", bool(project.project_id and project.workspace_path), "Project id and workspace metadata are present.")
    add("Semantic metadata", project.semantic_tables is not None, "Semantic table collection is available.")

    path_len = len(str(final_root))
    add("Safe path length", path_len < 190, f"Export root length is {path_len} characters.", warning=path_len >= 150)
    add("Validation metadata", project.validation_issues is not None, "Validation issue collection is available.")

    if blockers:
        raise ExportValidationError("Export pre-validation failed. " + " | ".join(blockers))
    return checks


def _commit_transaction(staging_root: Path, final_root: Path, temp_zip: Path, final_zip: Path) -> None:
    import os
    backup_root = final_root.with_name(final_root.name + ".previous")
    backup_zip = final_zip.with_suffix(final_zip.suffix + ".previous")
    for old in (backup_root, backup_zip):
        if old.is_dir():
            shutil.rmtree(old, ignore_errors=True)
        elif old.exists():
            old.unlink(missing_ok=True)

    moved_root = False
    moved_zip = False
    try:
        if final_root.exists():
            os.replace(final_root, backup_root)
        if final_zip.exists():
            os.replace(final_zip, backup_zip)
        os.replace(staging_root, final_root)
        moved_root = True
        os.replace(temp_zip, final_zip)
        moved_zip = True
        if backup_root.exists():
            shutil.rmtree(backup_root, ignore_errors=True)
        backup_zip.unlink(missing_ok=True)
    except Exception:
        if moved_zip and final_zip.exists():
            final_zip.unlink(missing_ok=True)
        if moved_root and final_root.exists():
            shutil.rmtree(final_root, ignore_errors=True)
        if backup_root.exists():
            os.replace(backup_root, final_root)
        if backup_zip.exists():
            os.replace(backup_zip, final_zip)
        raise


def _sql_validation_rows(project: MigrationProject) -> list[dict]:
    rows = []
    mapping_by_source = {m.source_id: m for m in project.source_mappings}
    for t in project.semantic_tables:
        if not t.include_in_export:
            continue
        m = mapping_by_source.get(t.source_id)
        if not m or m.target_connector not in {"SQL Server", "Azure SQL"}:
            continue
            
        m_query = t.m_query or ""
        has_sql_db = "Sql.Database" in m_query
        has_data = "[Data]" in m_query or "Value.NativeQuery" in m_query
        
        server = (m.server_name or "").strip()
        db = (m.database_name or "").strip()
        schema = (m.schema_name or "").strip()
        table = (m.table_name or "").strip()
        
        rows.append({
            "Server": server if server else "Missing",
            "Database": db if db else "Missing",
            "Schema": schema if schema else "dbo",
            "Source table": table if table else "Missing",
            "Generated Power Query partition": m_query,
            "Valid SQL Navigation": "Yes" if has_sql_db and has_data else "No"
        })
    return rows


def write_export(project: MigrationProject) -> Path:
    import tempfile

    workspace = Path(project.workspace_path).resolve()
    exports_dir = (workspace / "exports").resolve()
    export_id = _short_export_id(project)
    # Do not use the Tableau/workbook name for physical export paths. A friendly name is
    # retained in reports/metadata, while the PBIP itself stays safe under Windows MAX_PATH.
    package_stem = f"T2PBI_{export_id}"
    final_root = (exports_dir / package_stem).resolve()
    final_zip = (exports_dir / f"{package_stem}.zip").resolve()
    portable = _portable_pbip_paths(export_id)

    prevalidation = _export_prevalidate(project, workspace, exports_dir, final_root)
    deepest_internal = str(portable["deepest_expected"]).replace("\\", "/")
    # Keep the portable path tiny so the package can still open after extraction inside
    # a long Downloads/OneDrive/customer folder. 90 leaves ~150 chars of headroom.
    if len(deepest_internal) > 90:
        raise ExportValidationError(f"Internal PBIP path budget exceeded: {deepest_internal}")
    prevalidation.append({"check": "Portable PBIP internal path", "status": "Passed", "message": f"Deepest expected internal Power BI path is {len(deepest_internal)} characters: {deepest_internal}"})
    staging_root = Path(tempfile.mkdtemp(prefix=".t2pbi_export_", dir=str(exports_dir))).resolve()
    temp_zip = exports_dir / f".{package_stem}.{project.project_id}.tmp.zip"
    session = _ExportSession(project, staging_root, final_root, final_zip)
    session.prevalidation = prevalidation

    try:
        session.write_json("lineage/project_lineage.json", project.model_dump())
        session.write_json("inventory/file_inventory.json", [i.model_dump() for i in project.inventory])
        session.write_json("validation/validation_report.json", [i.model_dump() for i in project.validation_issues])
        session.write_json("source_mapping/source_mapping.json", [m.model_dump() for m in project.source_mappings])
        export_semantic_tables = _prepare_export_semantic_tables(project)
        session.write_json("semantic_model/semantic_tables.json", [t.model_dump() for t in export_semantic_tables])
        session.write_json("visuals/visual_build_plan.json", project.visual_plan)
        session.write_json("migration_strategy/migration_decisions.json", project.migration_decisions)
        session.write_json("migration_strategy/tde_extract_strategy.json", getattr(project, "tde_analysis", []))
        session.write_json("migration_strategy/tde_recovered_logic.json", [t.get("recovered_logic_detail", {}) for t in getattr(project, "tde_analysis", [])])
        session.write_json("lineage/tde_source_lineage.json", getattr(project, "tde_analysis", []))
        session.write_json("validation/reconciliation_plan.json", project.reconciliation_plan)
        session.write_json("validation/tde_reconciliation_plan.json", [p for p in project.reconciliation_plan if str(p.get("step", "")).upper() == "TDE"])
        session.write_json("validation/tde_baseline_metrics.json", [t.get("baseline_metrics", {}) for t in getattr(project, "tde_analysis", [])])
        session.write_csv("manual_review/tde_manual_review_items.csv", _tde_manual_review_rows(project))
        session.write_csv("source_mapping/tde_source_mapping.csv", _flatten_tde_rows(project))
        session.write_csv("validation/tde_source_column_validation.csv", _tde_column_validation_rows(project))
        session.write_json("validation/tde_source_column_validation.json", _tde_column_validation_rows(project))

        # Bundle available source data files into the exported package for seamless offline/local refresh
        for item in project.inventory:
            if item.extension.lower() in {".xlsx", ".xls", ".csv", ".txt", ".tsv", ".json", ".xml", ".parquet", ".sql"}:
                src_file = Path(item.absolute_path)
                if src_file.exists() and src_file.is_file():
                    folder_rel = item.folder_path.strip("/\\") if item.folder_path and item.folder_path not in {".", ""} else "Data"
                    rel_dest = Path(folder_rel) / item.file_name
                    dest_path = staging_root / rel_dest
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_path)
                    session.record(dest_path, "Success", f"Bundled source data file {item.file_name}", dest_path.stat().st_size)

        
        # Build valid table columns for reference validation in the report
        valid_table_cols_ci = {}
        for t in export_semantic_tables:
            if t.include_in_export:
                valid_table_cols_ci[t.name.casefold()] = {str(c.get("name") or "").casefold() for c in t.columns}
        
        import re
        def _refs_valid(expr: str) -> list[str]:
            if not expr: return []
            refs = re.findall(r"'([^']+)'\[([^\]]+)\]", expr)
            missing = []
            for tbl, col in refs:
                t_key, c_key = tbl.casefold(), col.casefold()
                if t_key not in valid_table_cols_ci:
                    missing.append(f"Table '{tbl}'")
                elif c_key not in valid_table_cols_ci[t_key]:
                    missing.append(f"Column '{tbl}'[{col}]")
            return missing

        calc_validation_rows = []
        for calc in project.calculations:
            is_safe = _safe_dax_expression(calc.generated_expression)
            missing_refs = _refs_valid(calc.generated_expression)
            refs_are_valid = len(missing_refs) == 0
            
            if calc.confidence_score >= 0.70 and is_safe and refs_are_valid:
                status = "Migrated"
            elif calc.confidence_score > 0 and calc.confidence_score < 0.70:
                status = "Manual Review"
            elif not is_safe or not refs_are_valid:
                status = "Failed"
            else:
                status = "Unsupported"
                
            warnings = calc.warnings.copy() if calc.warnings else []
            if not refs_are_valid:
                warnings.append("Missing DAX references: " + ", ".join(missing_refs))
                
            calc_validation_rows.append({
                "calculation_name": calc.name,
                "datasource": calc.datasource,
                "formula": calc.formula,
                "generated_dax": calc.generated_expression,
                "target_type": calc.target_object_type,
                "confidence": calc.confidence_score,
                "status": status,
                "warnings": "; ".join(warnings),
                "dax_safe": is_safe,
                "references_valid": refs_are_valid
            })
        session.write_csv("validation/calculation_validation.csv", calc_validation_rows)
        
        sql_validation_rows = _sql_validation_rows(project)
        if sql_validation_rows:
            session.write_csv("validation/sql_partition_validation.csv", sql_validation_rows)
        
        session.write_text("migration_strategy/tde_rebuild_plan.md", _tde_rebuild_plan(project))
        session.write_text("docs/APPLICATION_INPUT_GUIDE.md", _application_capability_guide())
        session.write_text("Migration_Report.md", _migration_report(project))

        used_names: set[str] = set()
        for idx, table in enumerate(export_semantic_tables, start=1):
            stem = _safe_file_stem(table.name or f"Table_{idx}", max_len=55)
            while stem.lower() in used_names:
                stem = _safe_file_stem(f"{table.name}_{idx}", max_len=55)
            used_names.add(stem.lower())
            session.write_text(Path("m_queries") / f"{stem}.pq", table.m_query or "")

        used_dax: set[str] = set()
        for idx, calc in enumerate(project.calculations, start=1):
            target_folder = "dax" if (calc.target_object_type in {"measure", "calculated_column"} and calc.confidence_score >= 0.70) else "manual_review"
            stem = _safe_file_stem(calc.name or f"Calculation_{idx}", max_len=55)
            while stem.lower() in used_dax:
                stem = _safe_file_stem(f"{calc.name}_{idx}", max_len=55)
            used_dax.add(stem.lower())
            expression = calc.generated_expression or "/* Manual review required */"
            session.write_text(Path(target_folder) / f"{stem}.dax", f"// Tableau formula:\n// {calc.formula}\n\n{clean_name(calc.name)} = {expression}\n")

        pbip_root = portable["root"]
        semantic_rel = portable["semantic"]
        report_rel = portable["report"]
        session.write_text(portable["pbip"], '{"version":"1.0","artifacts":[{"report":{"path":"./' + f'{export_id}.Report' + '"}}]}')
        session.write_text(semantic_rel / "definition.pbism", '{"version":"1.0"}')
        model_bim_dict = _model_bim(project, export_semantic_tables)
        total_model_measures = sum(len(t.get("measures", [])) for t in model_bim_dict.get("model", {}).get("tables", []))
        has_measures_expected = any(c.target_object_type in {"measure", "calculated measure"} for c in project.calculations)
        if has_measures_expected and total_model_measures == 0:
            raise ExportValidationError("Measures were generated but were not serialized into model.bim.")
        session.write_json(semantic_rel / "model.bim", model_bim_dict)
        session.write_text(report_rel / "definition.pbir", '{"version":"1.0","datasetReference":{"byPath":{"path":"../' + f'{export_id}.SemanticModel' + '"}}}')
        default_report_json = {
            "version": "1.0",
            "sections": [
                {
                    "name": "ReportSection1",
                    "displayName": "Page 1",
                    "width": 1280,
                    "height": 720,
                    "visualContainers": []
                }
            ]
        }
        session.write_json(report_rel / "report.json", default_report_json)

        # Final structural PBIP validation runs against the exact files that will be zipped.
        pbip_checks, pbip_blockers = validate_pbip_tree(staging_root / pbip_root)
        session.prevalidation.extend(pbip_checks)
        session.write_json("validation/pbip_integrity_validation.json", {"checks": pbip_checks, "blockers": pbip_blockers, "power_bi_desktop_validation": "Required after download; this runtime cannot launch Power BI Desktop."})
        if pbip_blockers:
            raise ExportValidationError("Final PBIP integrity validation failed. " + " | ".join(pbip_blockers))

        if getattr(project, "tde_analysis", []):
            session.warnings.append("Legacy TDE artifacts are retained for lineage and validation only; configure original sources before production refresh.")
            session.manual_actions.append("Review migration_strategy/tde_rebuild_plan.md and complete original-source mapping for each TDE.")
        if project.validation_issues:
            session.manual_actions.append("Review validation/validation_report.json and resolve blocking or business-validation items before production deployment.")
        if not export_semantic_tables:
            session.warnings.append("No semantic tables were generated; the PBIP contains a safe-mode skeleton and review artifacts only.")

        readme = f"""# Open First - TABLEAU2PBI Migration Package\n\nProject: {project.project_name}\nHealth: {project.health_status}\nExport Engine: 11.6.3 PBIP short-path + integrity-hardened transactional exporter\n\n## Start here\n1. Open ExportLog.html or ExportLog.json.\n2. Review validation/validation_report.json.\n3. Review source_mapping and TDE recovery artifacts.\n4. Open the PBIP only after mandatory source mappings are complete.\n\nSafe Openable Mode does not force unsupported Tableau logic into invalid Power BI artifacts.\n"""
        session.write_text("README_OPEN_FIRST.txt", readme)
        session.write_text("OPEN_THIS_PBIP.cmd", f"@echo off\nsetlocal\ncd /d %~dp0PBI\nstart \"\" \"{export_id}.pbip\"\nendlocal\n")
        session.write_logs("Success")

        temp_zip.unlink(missing_ok=True)
        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for file in sorted(staging_root.rglob("*")):
                if file.is_file():
                    # ZIP entries start at package root. Do not add another long project-name folder;
                    # Windows users commonly extract into a folder named after the ZIP already.
                    zf.write(file, file.relative_to(staging_root))
        _commit_transaction(staging_root, final_root, temp_zip, final_zip)
        return final_zip
    except Exception as exc:
        session.record(staging_root, "Error", f"Export aborted: {exc}")
        try:
            session.write_logs("Failed")
        except Exception:
            pass
        temp_zip.unlink(missing_ok=True)
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
