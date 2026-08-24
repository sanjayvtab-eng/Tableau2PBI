from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any
from app.core.name_sanitizer import clean_name
from app.models.schemas import MigrationProject, ValidationIssue

TABLEAU_GENERATED_FIELD_PATTERNS = {
    "measure names",
    "measure values",
    "number of records",
    "generated latitude",
    "generated longitude",
}

ROW_LEVEL_FUNCTIONS = {
    "ABS", "CEILING", "FLOOR", "ROUND", "ZN", "IFNULL", "ISNULL", "LEFT", "RIGHT", "MID",
    "LOWER", "UPPER", "TRIM", "LTRIM", "RTRIM", "DATE", "DATETRUNC", "DATEPART", "YEAR",
    "MONTH", "DAY", "INT", "FLOAT", "STR", "SPLIT", "REPLACE", "CONTAINS", "STARTSWITH", "ENDSWITH",
}
AGG_FUNCTIONS = {"SUM", "AVG", "AVERAGE", "COUNT", "COUNTD", "MIN", "MAX", "MEDIAN", "STDEV", "VAR", "PERCENTILE", "ATTR"}
TABLE_CALC_PATTERNS = ["WINDOW_", "RUNNING_", "LOOKUP", "INDEX", "FIRST()", "LAST()", "PREVIOUS_VALUE", "RANK", "TOTAL(", "SIZE()"]
LOD_PATTERNS = ["{FIXED", "{ FIXED", "{ INCLUDE", "{INCLUDE", "{ EXCLUDE", "{EXCLUDE", "FIXED ", "INCLUDE ", "EXCLUDE "]
RAW_SQL_PATTERNS = ["RAWSQL_"]
EXTERNAL_PATTERNS = ["SCRIPT_", "MODEL_EXTENSION_"]


def is_tableau_generated_field(field_name: str | None) -> bool:
    text = clean_name(field_name or "").lower().replace("_", " ")
    return text in TABLEAU_GENERATED_FIELD_PATTERNS or text.startswith("generated ")


def classify_formula_destination(formula: str | None) -> dict[str, Any]:
    """Compiler decision: source SQL vs M vs DAX vs visual/manual review."""
    f = (formula or "").strip()
    u = f.upper()
    if not f:
        return {"stage": "none", "decision": "No calculation formula", "confidence": 1.0, "manual_review": False}
    if any(p in u for p in EXTERNAL_PATTERNS):
        return {"stage": "manual_review", "decision": "External analytics/model-extension logic cannot be safely auto-converted", "confidence": 0.0, "manual_review": True}
    if any(p in u for p in RAW_SQL_PATTERNS):
        return {"stage": "source_sql_review", "decision": "RAWSQL should remain native SQL / Value.NativeQuery only after security and folding review", "confidence": 0.35, "manual_review": True}
    if any(p in u for p in TABLE_CALC_PATTERNS):
        return {"stage": "dax_measure_manual_review", "decision": "Table calculation depends on visual partition/addressing; convert to DAX measure and validate by visual", "confidence": 0.45, "manual_review": True}
    if any(p in u for p in LOD_PATTERNS):
        return {"stage": "dax_measure", "decision": "LOD should be converted to DAX CALCULATE/ALLEXCEPT/REMOVEFILTERS pattern and validated", "confidence": 0.70, "manual_review": True}
    if re.search(r"\b(" + "|".join(AGG_FUNCTIONS) + r")\s*\(", u):
        return {"stage": "dax_measure", "decision": "Aggregation belongs in DAX measure, not Power Query", "confidence": 0.90, "manual_review": False}
    return {"stage": "power_query_or_dax_column", "decision": "Row-level deterministic expression can be M calculated column or DAX calculated column", "confidence": 0.82, "manual_review": False}


def table_combination_decision(relation_type: str | None, custom_sql: str | None = None) -> dict[str, Any]:
    r = (relation_type or "").lower()
    if custom_sql or "text" == r or "custom" in r:
        return {"powerbi_target": "Value.NativeQuery / SQL view placeholder", "migration_decision": "Custom SQL requires source/security/folding review before production", "manual_review": True}
    if "join" in r:
        return {"powerbi_target": "Power Query Merge only when physical output is required", "migration_decision": "Physical join can flatten data; validate row count and grain", "manual_review": False}
    if "union" in r:
        return {"powerbi_target": "Power Query Append", "migration_decision": "Union/append same-structure tables", "manual_review": False}
    if "relationship" in r or "logical" in r or r in {"table", "relation"}:
        return {"powerbi_target": "Semantic model relationship", "migration_decision": "Do not convert Tableau relationship auto-join behavior into M merge", "manual_review": False}
    if "blend" in r or "federated" in r:
        return {"powerbi_target": "Semantic model / bridge table / composite model", "migration_decision": "Omit Tableau blending mechanics and rebuild model", "manual_review": True}
    return {"powerbi_target": "Review", "migration_decision": "Unknown table-combination logic", "manual_review": True}


def _is_tde_mapping(m: Any) -> bool:
    text = " ".join(str(x or "") for x in [getattr(m, "original_connection_type", ""), getattr(m, "detected_source_path", ""), getattr(m, "target_file_path", ""), getattr(m, "datasource", "")]).lower()
    return ".tde" in text or " tde" in text or "tableau extract .tde" in text or getattr(m, "mapping_status", "").lower().startswith("legacy tde")


def _is_extract_mapping(m: Any) -> bool:
    text = " ".join(str(x or "") for x in [getattr(m, "original_connection_type", ""), getattr(m, "detected_source_path", ""), getattr(m, "target_file_path", ""), getattr(m, "datasource", ""), getattr(m, "mapping_status", "")]).lower()
    return ".tde" in text or ".hyper" in text or "extract" in text or (getattr(m, "target_connector", "") == "Manual source placeholder" and ("dataengine" in text or "hyper" in text))


def _safe_read_json(path: str | Path) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def _tde_metadata_documents(project: MigrationProject) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for item in project.inventory:
        name = item.file_name.lower()
        if item.extension.lower() != ".json":
            continue
        if not ("tde" in name or "extract" in name or "lineage" in name or "migration" in name):
            continue
        if str(item.absolute_path).startswith("zip://"):
            continue
        data = _safe_read_json(item.absolute_path)
        if not isinstance(data, dict):
            continue
        signals = " ".join([name, str(data.get("tde_file", "")), str(data.get("extract_file", "")), str(data.get("upstream_sources", "")), str(data.get("recovered_logic", ""))]).lower()
        if "tde" in signals or "upstream" in signals or "extract" in signals:
            docs.append({"file_name": item.file_name, "folder_path": item.folder_path, "absolute_path": item.absolute_path, "content": data})
    return docs


def _metadata_for_tde(tde_file_name: str, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stem = Path(tde_file_name).stem.lower()
    result = []
    for doc in docs:
        c = doc.get("content", {})
        signals = " ".join([doc.get("file_name", ""), str(c.get("tde_file", "")), str(c.get("extract_file", "")), str(c.get("associated_tde", ""))]).lower()
        if stem in signals or not result:
            result.append(doc)
    return result


def _classify_extract_filter(filter_obj: dict[str, Any] | str) -> dict[str, Any]:
    text = str(filter_obj)
    u = text.upper()
    purpose = "Unknown / manual review"
    target = "Manual review - do not silently apply"
    reason = "Purpose cannot be safely inferred from metadata alone."
    if any(x in u for x in ["USER", "USERNAME", "ISMEMBEROF", "SECURITY", "DOMAIN"]):
        purpose = "Security rule"
        target = "Power BI Row-Level Security"
        reason = "Filter appears identity/security driven."
    elif any(x in u for x in ["DATE", "YEAR", "MONTH", "ORDERDATE", "INVOICE", "CUTOFF", "RANGE", "INCREMENTAL"]):
        purpose = "Historical cutoff"
        target = "Incremental refresh or source-side date filter"
        reason = "Filter appears date/cutoff driven."
    elif any(x in u for x in ["REGION", "COUNTRY", "CUSTOMER", "SEGMENT", "PRODUCT", "CATEGORY", "STATUS"]):
        purpose = "Business rule"
        target = "Power Query row filter or DAX filter depending on analytic intent"
        reason = "Filter appears business-domain driven."
    elif any(x in u for x in ["LIMIT", "TOP", "ROW", "SAMPLE", "EXTRACT"]):
        purpose = "Data volume reduction"
        target = "Source SQL / Power Query / dataflow filter"
        reason = "Filter appears designed to reduce volume."
    return {"filter": filter_obj, "purpose": purpose, "powerbi_target": target, "reason": reason}


def _metadata_lists(docs: list[dict[str, Any]], *keys: str) -> list[Any]:
    out: list[Any] = []
    for d in docs:
        c = d.get("content", {})
        for k in keys:
            val = c.get(k)
            if isinstance(val, list):
                out.extend(val)
            elif val:
                out.append(val)
    return out


def _metadata_dicts(docs: list[dict[str, Any]], *keys: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for d in docs:
        c = d.get("content", {})
        for k in keys:
            val = c.get(k)
            if isinstance(val, dict):
                out.update(val)
    return out


def _project_logic_summary(project: MigrationProject) -> dict[str, Any]:
    return {
        "connections": [c.model_dump() for ds in project.datasources for c in ds.connections],
        "custom_sql": [r.model_dump() for ds in project.datasources for r in ds.relations if r.custom_sql],
        "physical_joins": [r.model_dump() for ds in project.datasources for r in ds.relations if "join" in (r.relation_type or "").lower()],
        "logical_relationships": [r.model_dump() for ds in project.datasources for r in ds.relations if "relationship" in (r.relation_type or "").lower() or (r.relation_type or "").lower() in {"table", "relation"}],
        "unions": [r.model_dump() for ds in project.datasources for r in ds.relations if "union" in (r.relation_type or "").lower()],
        "data_source_filters": [f for ds in project.datasources for f in ds.filters],
        "calculated_fields": [c.model_dump() for c in project.calculations],
        "parameters": [p.model_dump() for p in project.parameters],
        "worksheets": [w.model_dump() for w in project.worksheets],
        "dashboards": [d.model_dump() for d in project.dashboards],
    }


def _source_column_validation(project: MigrationProject, recovered_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate columns pulled from recovered/original sources against Tableau fields/calculations.

    This does not depend on the TDE file. It compares preview/profile columns from the
    original source mapping with Tableau metadata fields and calculation dependencies, then
    flags missing/unmatched fields for review.
    """
    preview_by_source = {p.source_id: p for p in project.previews}
    field_names = sorted({(f.caption or f.name or '').strip() for ds in project.datasources for f in ds.fields if (f.caption or f.name)})
    calc_dependencies = sorted({dep.strip('[]') for c in project.calculations for dep in c.dependencies if dep})
    required = sorted(set(field_names + calc_dependencies))
    required_norm = {clean_name(x).lower(): x for x in required}
    rows: list[dict[str, Any]] = []
    for src in recovered_sources:
        src_name = str(src.get('source_name') or src.get('name') or src.get('datasource') or '')
        # Prefer an exact source mapping, then table/path fuzzy match.
        mapping = next((m for m in project.source_mappings if clean_name(m.datasource).lower() == clean_name(src_name).lower()), None)
        if mapping is None:
            mapping = next((m for m in project.source_mappings if clean_name(src_name).lower() in clean_name(m.datasource).lower() or clean_name(m.datasource).lower() in clean_name(src_name).lower()), None)
        preview = preview_by_source.get(mapping.source_id) if mapping else None
        preview_columns = [c.column_name for c in preview.columns] if preview and preview.available else []
        preview_norm = {clean_name(c).lower(): c for c in preview_columns}
        matched = []
        missing = []
        for n, original in required_norm.items():
            if n in preview_norm:
                matched.append({'tableau_field': original, 'source_column': preview_norm[n], 'match_type': 'exact_normalized'})
            elif src_name and clean_name(src_name).lower() in n:
                missing.append(original)
        # If no Tableau field matched by source name, still provide a general validation summary.
        status = 'No local preview available'
        if preview and preview.available:
            status = 'Validated' if preview_columns else 'Preview has no columns'
            if missing:
                status = 'Validated with missing Tableau fields'
        rows.append({
            'source_name': src_name or (mapping.datasource if mapping else 'Unknown source'),
            'source_id': mapping.source_id if mapping else None,
            'target_connector': mapping.target_connector if mapping else src.get('source_type'),
            'source_path_or_table': (mapping.target_file_path or mapping.detected_source_path or mapping.table_name) if mapping else src.get('detected_source_path'),
            'preview_available': bool(preview and preview.available),
            'source_column_count': len(preview_columns),
            'source_columns': preview_columns,
            'matched_tableau_columns': matched[:100],
            'missing_tableau_fields_for_review': missing[:100],
            'status': status,
            'warnings': (preview.warnings if preview else ['Source details must be provided and saved, then preview regenerated.']),
        })
    return rows


def build_tde_analysis(project: MigrationProject) -> list[dict[str, Any]]:
    """Analyze .tde as a legacy output artifact/snapshot and recover upstream source logic from metadata when possible."""
    tde_files = [i for i in project.inventory if i.extension.lower() == ".tde"]
    if not tde_files:
        return []

    metadata_files = [i for i in project.inventory if i.extension.lower() in {".twb", ".twbx", ".tds", ".tdsx", ".tfl", ".tflx"}]
    meta_docs = _tde_metadata_documents(project)
    non_extract_mappings = [m for m in project.source_mappings if not _is_extract_mapping(m) and getattr(m, "target_connector", "") != "Manual source placeholder"]
    custom_sql_objects = []
    for ds in project.datasources:
        for r in ds.relations:
            if r.custom_sql:
                custom_sql_objects.append({"datasource": ds.name, "relation": r.name, "source": "tableau_relation_custom_sql", "sql": r.custom_sql})
    for m in project.source_mappings:
        if m.sql_query:
            custom_sql_objects.append({"datasource": m.datasource, "source_id": m.source_id, "source": "source_mapping_sql", "sql": m.sql_query})

    project_logic = _project_logic_summary(project)
    source_names = sorted({m.datasource for m in non_extract_mappings})
    has_metadata = bool(metadata_files)
    has_original_sources = bool(non_extract_mappings)
    has_custom_sql = bool(custom_sql_objects)
    has_multiple_sources = len(source_names) > 1 or len([m for m in project.source_mappings if not _is_tde_mapping(m)]) > 1

    analyses: list[dict[str, Any]] = []
    for item in tde_files:
        docs = _metadata_for_tde(item.file_name, meta_docs)
        meta_sources = _metadata_lists(docs, "upstream_sources", "original_sources", "recovered_sources")
        meta_transformations = _metadata_lists(docs, "transformations", "prep_steps", "extract_creation_steps")
        meta_extract_filters = _metadata_lists(docs, "extract_filters")
        meta_baseline = _metadata_dicts(docs, "baseline_metrics", "tde_baseline_metrics")
        meta_incremental = _metadata_dicts(docs, "incremental_refresh")

        recovered_sources = []
        for m in non_extract_mappings:
            recovered_sources.append({
                "source_name": m.datasource,
                "source_type": m.target_connector,
                "connection_recovered_from": m.parameter_values.get("source", "Tableau metadata / uploaded source inventory"),
                "detected_source_path": m.detected_source_path or m.target_file_path,
                "server": m.server_name,
                "database": m.database_name,
                "schema": m.schema_name,
                "table": m.table_name,
                "recommended_powerbi_connector": m.target_connector,
                "migration_target": "Power Query / Dataflow / SQL View / Fabric staging",
            })
        for src in meta_sources:
            if isinstance(src, dict):
                src2 = dict(src)
                src2.setdefault("connection_recovered_from", "TDE metadata companion file")
                src2.setdefault("migration_target", "Power Query / Dataflow / SQL View / Fabric staging")
                recovered_sources.append(src2)
            else:
                recovered_sources.append({"source_name": str(src), "connection_recovered_from": "TDE metadata companion file", "migration_target": "Power Query / Dataflow / SQL View / Fabric staging"})

        # Deduplicate sources by name/type/path.
        dedup_sources: dict[str, dict[str, Any]] = {}
        for s in recovered_sources:
            key = "|".join(str(s.get(k, "")).lower() for k in ["source_name", "source_type", "detected_source_path", "server", "database", "table"])
            dedup_sources[key] = s
        recovered_sources = list(dedup_sources.values())

        extract_filter_objs = list(meta_extract_filters) + project_logic["data_source_filters"]
        extract_filter_classification = [_classify_extract_filter(f) for f in extract_filter_objs]

        scenario = "Case D - only TDE available"
        decision = "Treat the .tde as a legacy frozen snapshot. Use Tableau Desktop 2024.2 or older to export to CSV/Hyper/database table only as a temporary fallback."
        priority = "Fallback only"
        if has_original_sources or recovered_sources:
            scenario = "Case A - original sources available"
            decision = "Rebuild from original database/file/cloud sources. Use .tde only as validation baseline for row counts, totals, and business results."
            priority = "Preferred production path"
        if has_custom_sql:
            scenario = "Case B - original SQL/custom SQL available" if not has_multiple_sources else "Case B/C - SQL plus multiple sources"
            decision = "Move custom SQL to database view, Power Query native query, dataflow, Fabric pipeline, or staging table; do not hide complex transformation only inside the report."
            priority = "Preferred if SQL is authoritative"
        if (has_multiple_sources or len(recovered_sources) > 1) and tde_files:
            scenario = "Case C - TDE created from multiple sources" if not has_metadata else "Case C/E - TDE plus metadata with multiple upstream sources"
            decision = "Ignore the TDE as a production source. Rebuild each upstream source separately, recreate filters/joins/unions/calculations in Power Query/SQL/Dataflow/Fabric/DAX, and create a clean Power BI semantic model/star schema."
            priority = "Production redesign required"
        if has_metadata and not (has_original_sources or recovered_sources) and not has_custom_sql:
            scenario = "Case E - TDE plus Tableau metadata available"
            decision = "Use .twb/.tds metadata to recover original connection, join, relationship, filter, alias, group, and calculation logic, then map to Power BI sources."
            priority = "Recover source logic before build"

        recovered_logic_flags = {
            "connections": bool(project_logic["connections"] or recovered_sources),
            "custom_sql": bool(project_logic["custom_sql"] or custom_sql_objects),
            "joins": bool(project_logic["physical_joins"]),
            "relationships": bool(project_logic["logical_relationships"]),
            "unions": bool(project_logic["unions"]),
            "extract_filters": bool(extract_filter_objs),
            "calculated_fields": bool(project.calculations),
            "lod_calculations": any("FIXED" in c.formula.upper() or "INCLUDE" in c.formula.upper() or "EXCLUDE" in c.formula.upper() for c in project.calculations),
            "table_calculations": any(any(p in c.formula.upper() for p in TABLE_CALC_PATTERNS) for c in project.calculations),
            "incremental_refresh_key": bool(meta_incremental),
            "metadata_companion_file": bool(docs),
        }

        tde_file = {
            "file_name": item.file_name,
            "folder_path": item.folder_path,
            "size_bytes": item.size_bytes,
            "role": item.role,
            "associated_workbook": item.associated_workbook,
            "associated_data_source": item.associated_data_source,
            "associated_extract_or_source": item.associated_extract_or_source,
            "legacy_extract_status": "Legacy Tableau .tde extract artifact",
            "source_of_truth": False,
            "powerbi_dependency_allowed": False,
            "recommended_usage": "Validation baseline / temporary static fallback only",
            "fallback_use": "Export from Tableau Desktop 2024.2 or older to CSV/Hyper/database table only if original sources are unavailable",
        }

        analysis = {
            "tde_file": item.file_name,
            "tde_role": "Legacy extract snapshot / validation baseline",
            "is_source_of_truth": False,
            "recommended_usage": "Validation reference only. Ignore TDE for production if original sources/metadata are available.",
            "scenario": scenario,
            "scenario_classification": scenario,
            "priority": priority,
            "decision": decision,
            "preferred_architecture": "Original source systems -> reusable transformation layer (Power Query/Dataflow/Fabric/SQL staging) -> clean Power BI semantic model/star schema -> DAX measures -> reports",
            "temporary_fallback": "TDE -> Tableau Desktop 2024.2 or older -> export to CSV/Hyper/database table -> Power BI Import model",
            "validation_pattern": "Tableau report using TDE totals compared with Power BI report using rebuilt source logic",
            "tde_files": [tde_file],
            "metadata_files_found": [f.file_name for f in metadata_files],
            "tde_metadata_companion_files": [d.get("file_name") for d in docs],
            "original_sources_detected": source_names,
            "recovered_sources": recovered_sources,
            "source_column_validation": _source_column_validation(project, recovered_sources),
            "custom_sql_detected": custom_sql_objects,
            "multiple_upstream_sources_detected": has_multiple_sources or len(recovered_sources) > 1,
            "recovered_logic": recovered_logic_flags,
            "recovered_logic_detail": {
                "from_tableau_metadata": project_logic,
                "from_tde_companion_metadata": [d.get("content", {}) for d in docs],
                "inferred_from_file_structure": [m.model_dump() for m in project.source_mappings],
                "available_only_from_tde_snapshot": ["final extracted rows", "snapshot row count", "baseline totals when readable/exported"],
                "not_recoverable_from_tde_alone": ["original SQL if not in metadata", "upstream joins if metadata missing", "business purpose of filters", "Tableau table calculation addressing", "server credentials"],
            },
            "extract_filter_classification": extract_filter_classification,
            "baseline_metrics": meta_baseline,
            "incremental_refresh": meta_incremental,
            "powerbi_rebuild_strategy": {
                "architecture": "Original sources -> transformation layer -> semantic model/star schema -> DAX -> reports",
                "storage_mode_recommendation": "Import first; DirectQuery/Hybrid/Direct Lake/composite only when data volume, latency, and platform justify it",
                "star_schema_recommended": True,
                "use_tde_directly": False,
                "reason": "TDE is an output artifact and not a refreshable enterprise Power BI source.",
            },
            "fallback_strategy": {
                "required_only_if_original_sources_unavailable": True,
                "steps": [
                    "Open TDE using Tableau Desktop 2024.2 or older",
                    "Export to CSV, Hyper, or database table",
                    "Load exported file into Power BI Import model",
                    "Mark report as historical/static unless refresh source is rebuilt",
                ],
            },
            "source_recovery_checklist": [
                "Identify original connections from TWB/TDS/TWBX/TDSX/TFL/TFLX metadata.",
                "Recover custom SQL, physical joins, logical relationships, unions, blends, source filters, and extract filters.",
                "Recover field renames, hidden fields, aliases, groups, data type changes, split/pivot/unpivot logic, extract aggregation, row limits, and incremental refresh keys.",
                "Classify every calculation as Power Query row-level/data-cleanup, DAX column, DAX measure, LOD measure, table-calculation measure/manual-review, or visual-layer logic.",
                "Build Power BI as original sources -> reusable transformation/staging layer -> semantic model/star schema -> DAX -> reports.",
                "Use the TDE only to validate row counts, distinct key counts, totals, filtered totals, Top N, percent-of-total, LOD, and table-calculation outputs.",
            ],
            "validation_checkpoints": [
                "TDE row count vs source row count vs Power BI imported row count",
                "Distinct key count, duplicate count, null count",
                "Sales/revenue/quantity/record totals",
                "Totals by month, region, customer, product",
                "Grand totals and filtered totals",
                "Top N and percent-of-total results",
                "LOD calculation outputs",
                "Table calculation outputs such as running totals, rank, moving average, and window calculations",
            ],
            "omit_rules": [
                "Do not use .tde as main source of truth.",
                "Do not treat .tde as refreshable enterprise source.",
                "Do not convert every Tableau relationship into Power Query Merge.",
                "Do not flatten every Tableau join unless physical output is required.",
                "Do not recreate Tableau blending literally; use model relationships, bridge tables, composite models, or staged data.",
                "Do not migrate extract filters blindly; classify them as volume, security, business rule, or historical cutoff.",
                "Do not convert aggregate/LOD/table calculations into static Power Query columns.",
            ],
            "manual_review_required": [
                "Unknown extract filter purpose",
                "Table calculation addressing/partitioning",
                "LOD context differences",
                "Missing original credentials",
                "TDE-only report where original source/metadata is not provided",
            ],
        }
        analyses.append(analysis)
    return analyses


def build_migration_decisions(project: MigrationProject) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []

    for ds in project.datasources:
        for rel in ds.relations:
            d = table_combination_decision(rel.relation_type, rel.custom_sql)
            rel.warnings = list(dict.fromkeys(rel.warnings + [d["migration_decision"]]))
            decisions.append({
                "category": "table_combination",
                "datasource": ds.name,
                "object_name": rel.name,
                "tableau_type": rel.relation_type,
                "powerbi_target": d["powerbi_target"],
                "migration_decision": d["migration_decision"],
                "manual_review": d["manual_review"],
            })
        if any((c.connection_type or "").lower() in {"federated", "sqlproxy"} for c in ds.connections):
            decisions.append({
                "category": "blend_or_federated_source",
                "datasource": ds.name,
                "object_name": ds.name,
                "tableau_type": "federated/blend-like source",
                "powerbi_target": "semantic model / bridge table / composite model",
                "migration_decision": "Do not copy Tableau primary/secondary blending mechanics; rebuild as a Power BI model pattern.",
                "manual_review": True,
            })

    for calc in project.calculations:
        d = classify_formula_destination(calc.formula)
        decisions.append({
            "category": "calculation",
            "datasource": calc.datasource,
            "object_name": calc.name,
            "tableau_formula": calc.formula,
            "powerbi_target": d["stage"],
            "migration_decision": d["decision"],
            "confidence": d["confidence"],
            "manual_review": d["manual_review"],
        })
        if d["manual_review"] and d["decision"] not in calc.manual_review_notes:
            calc.manual_review_notes.append(d["decision"])

    for p in project.parameters:
        decisions.append({
            "category": "parameter",
            "object_name": p.name,
            "powerbi_target": p.powerbi_strategy,
            "migration_decision": "Use disconnected table / what-if / field parameter where appropriate; use Power Query parameter only for source-level parameters.",
            "manual_review": False,
        })

    for ds in project.datasources:
        generated = [f.name for f in ds.fields if is_tableau_generated_field(f.name)]
        if generated:
            decisions.append({
                "category": "omit_rule",
                "datasource": ds.name,
                "object_name": ", ".join(generated),
                "powerbi_target": "omit unless business-used",
                "migration_decision": "Tableau-generated fields such as Measure Names/Values or generated latitude/longitude are not migrated blindly.",
                "manual_review": False,
            })

    for row in build_tde_analysis(project):
        decisions.append({
            "category": "tde_strategy",
            "object_name": row.get("tde_file"),
            "tableau_type": "Legacy Tableau .tde extract",
            "powerbi_target": "ignore as production source; validation baseline/fallback only",
            "migration_decision": row.get("decision"),
            "scenario": row.get("scenario"),
            "manual_review": True,
        })
        decisions.append({
            "category": "tde_rebuild_architecture",
            "object_name": row.get("tde_file"),
            "powerbi_target": row.get("preferred_architecture"),
            "migration_decision": "Recover original sources and rebuild the reusable transformation layer before building the Power BI semantic model.",
            "manual_review": False,
        })
    return decisions


def build_reconciliation_plan(project: MigrationProject) -> list[dict[str, Any]]:
    tables = [t.name for t in project.semantic_tables]
    plan: list[dict[str, Any]] = [
        {"step": 1, "checkpoint": "Source row counts", "validation": "Compare Tableau source/extract rows with Power BI source rows for each mapped table.", "tables": tables},
        {"step": 2, "checkpoint": "Transformation grain", "validation": "Validate row count after filters, joins, unions/appends, pivots/unpivots, and calculated columns.", "tables": tables},
        {"step": 3, "checkpoint": "Relationship behavior", "validation": "Validate fact/dimension grain, cardinality, active/inactive relationships, and cross-filter direction. Do not expect Tableau relationship auto-join behavior to match without modeling review.", "tables": tables},
        {"step": 4, "checkpoint": "Measures and LOD", "validation": "Compare Tableau totals vs DAX totals at dashboard, sheet, and grain levels, especially FIXED/INCLUDE/EXCLUDE and Top N/context-filter visuals.", "calculations": [c.name for c in project.calculations if c.target_object_type.startswith("measure")]},
        {"step": 5, "checkpoint": "Visual behavior", "validation": "Validate filters, slicers, actions, tooltip logic, table calculations, rank/running totals, and percent-of-total calculations by visual.", "worksheets": [w.name for w in project.worksheets]},
        {"step": 6, "checkpoint": "Export openability", "validation": "Open PBIP safe-mode package and confirm unsupported logic is preserved in reports instead of causing invalid Power BI artifacts.", "health": project.health_status},
    ]
    for row in build_tde_analysis(project):
        plan.insert(1, {
            "step": "TDE",
            "checkpoint": "TDE validation baseline",
            "validation": "Compare TDE row count, distinct keys, nulls/duplicates, sales/revenue/quantity totals, month/region/customer/product totals, Top N, percent-of-total, LOD, and table-calculation outputs against the rebuilt Power BI model.",
            "artifact_rule": "Do not use TDE as the refreshable production source.",
            "tde_file": row.get("tde_file"),
            "baseline_metrics": row.get("baseline_metrics", {}),
        })
    return plan


def add_strategy_validation_issues(project: MigrationProject, decisions: list[dict[str, Any]]) -> None:
    existing = {(i.category, i.object_name, i.message) for i in project.validation_issues}
    for d in decisions:
        if d.get("manual_review"):
            msg = d.get("migration_decision") or "Manual review required."
            key = ("Migration Strategy", d.get("object_name") or project.project_name, msg)
            if key not in existing:
                project.validation_issues.append(ValidationIssue(
                    severity="warning",
                    category="Migration Strategy",
                    object_name=d.get("object_name") or project.project_name,
                    message=msg,
                    recommended_fix="Review the generated migration_decisions.json and validate result against Tableau before sign-off.",
                    auto_fixable=False,
                ))
                existing.add(key)


def add_tde_validation_issues(project: MigrationProject, analysis: list[dict[str, Any]]) -> None:
    if not analysis:
        return
    existing = {(i.category, i.object_name, i.message) for i in project.validation_issues}
    for row in analysis:
        msg = "Legacy .tde detected. It will be ignored as a production source and used only as validation baseline or temporary fallback."
        key = ("TDE Strategy", row.get("tde_file") or project.project_name, msg)
        if key not in existing:
            project.validation_issues.append(ValidationIssue(
                severity="warning",
                category="TDE Strategy",
                object_name=row.get("tde_file") or project.project_name,
                message=msg,
                recommended_fix=row.get("decision") or "Recover original sources and transformation logic before production migration.",
                auto_fixable=False,
            ))
            existing.add(key)
        if str(row.get("scenario", "")).startswith("Case D"):
            msg2 = "Only .tde appears available. Ongoing scheduled refresh should not depend on TDE; use Tableau Desktop export only as temporary/static fallback."
            key2 = ("TDE Strategy", row.get("tde_file") or project.project_name, msg2)
            if key2 not in existing:
                project.validation_issues.append(ValidationIssue(
                    severity="warning",
                    category="TDE Strategy",
                    object_name=row.get("tde_file") or project.project_name,
                    message=msg2,
                    recommended_fix="Ask business/source owners for original database/files/cloud sources or Tableau metadata. If unavailable, export TDE to CSV/Hyper/database table for static historical reporting.",
                    auto_fixable=False,
                ))
                existing.add(key2)
        unknown_filters = [f for f in row.get("extract_filter_classification", []) if str(f.get("purpose", "")).startswith("Unknown")]
        if unknown_filters:
            msg3 = f"{len(unknown_filters)} TDE/extract filter(s) require purpose classification before migration."
            key3 = ("TDE Extract Filters", row.get("tde_file") or project.project_name, msg3)
            if key3 not in existing:
                project.validation_issues.append(ValidationIssue(
                    severity="warning",
                    category="TDE Extract Filters",
                    object_name=row.get("tde_file") or project.project_name,
                    message=msg3,
                    recommended_fix="Classify each extract filter as volume reduction, security, business rule, historical cutoff, or manual review before applying it in Power BI.",
                    auto_fixable=False,
                ))
                existing.add(key3)
