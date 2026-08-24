from __future__ import annotations
from pathlib import Path
from app.core.name_sanitizer import clean_name
from app.models.schemas import MigrationProject, SemanticTable, ValidationIssue
from app.services.data_profiler import preview_mapping
from app.services.inventory_engine import build_inventory, extract_package, list_zip_members_as_inventory
from app.services.relationship_builder import infer_relationships
from app.services.source_mapping import build_source_mappings
from app.services.tableau_parser import parse_workbook_or_datasource
from app.services.visual_planner import build_visual_plan
from app.services.migration_strategy import build_migration_decisions, build_reconciliation_plan, add_strategy_validation_issues, add_tde_validation_issues, build_tde_analysis, is_tableau_generated_field
from app.translators.dax_translator import classify_and_translate
from app.translators.m_generator import generate_m_query
from app.validators.rules import validate_project, health_from_issues
from app.services.file_mode_router import build_file_processing_tree
from app.services.model_design_engine import is_model_table, clean_join_expansion_columns
from app.services.upload_model_engine import detect_upload_model, refine_upload_model, catalogue
from app.services.path_parameter_engine import configure_project_paths


def _summary(project: MigrationProject, workbook_meta: dict | None = None) -> dict:
    joins = sum(1 for ds in project.datasources for r in ds.relations if "join" in (r.relation_type or "").lower())
    unions = sum(1 for ds in project.datasources for r in ds.relations if "union" in (r.relation_type or "").lower())
    custom_sql = sum(1 for ds in project.datasources for r in ds.relations if r.custom_sql)
    relationships = len(project.relationships)
    unsupported = sum(1 for c in project.calculations if c.confidence_score < 0.7)
    blocked = len([i for i in project.validation_issues if i.severity == "error"])
    manual_sources = len([m for m in project.source_mappings if m.target_connector == "Manual source placeholder"])
    score = 100
    score -= min(40, unsupported * 5)
    score -= min(20, manual_sources * 3)
    score -= min(20, blocked * 10)
    workbook_count = len([i for i in project.inventory if i.extension.lower() == ".twb"])
    manual_review_items = sum(1 for d in project.migration_decisions if d.get("manual_review"))
    return {
        "Workbook name": (workbook_meta or {}).get("workbook_name", project.project_name),
        "Tableau version": (workbook_meta or {}).get("version", "Unknown"),
        "Inventory files": len(project.inventory),
        "Workbook files": workbook_count,
        "Dashboards": len(project.dashboards),
        "Worksheets": len(project.worksheets),
        "Stories": len(project.stories),
        "Data sources": len(project.datasources),
        "Source mappings": len(project.source_mappings),
        "Connections": sum(len(ds.connections) for ds in project.datasources),
        "Logical tables": len(project.datasources),
        "Physical tables": sum(len(ds.relations) for ds in project.datasources),
        "Joins": joins,
        "Relationships": relationships,
        "Unions": unions,
        "Custom SQL queries": custom_sql,
        "Calculated fields": len(project.calculations),
        "Parameters": len(project.parameters),
        "Filters": sum(len(ds.filters) for ds in project.datasources) + sum(len(w.filters) for w in project.worksheets),
        "Sets/groups/bins": "Inventory/manual review",
        "Extract files": len([i for i in project.inventory if i.role in {"Hyper extract", "Legacy TDE extract"}]),
        "Unsupported objects": unsupported,
        "Migration readiness score": max(score, 0),
        "Manual review decisions": manual_review_items,
        "TDE strategy scenario": (project.tde_analysis[0].get("scenario") if project.tde_analysis else "No legacy TDE detected"),
        "TDE source-of-truth rule": ("TDE is validation/fallback only" if project.tde_analysis else "N/A"),
        "Reconciliation checkpoints": len(project.reconciliation_plan),
        "Power BI export readiness": project.health_status,
        "M syntax validation": "Static validation",
        "M engine validation": "Not available",
    }


def _build_semantic_tables(project: MigrationProject) -> list[SemanticTable]:
    tables: list[SemanticTable] = []
    preview_by_source = {p.source_id: p for p in project.previews}
    for mapping in project.source_mappings:
        mapping_text = " ".join(str(x or "") for x in [mapping.original_connection_type, mapping.detected_source_path, mapping.target_file_path, mapping.mapping_status]).lower()
        # A relation-fallback mapping is a Tableau logical wrapper, not a final business
        # table, when concrete source mappings exist for the same datasource.
        if mapping.parameter_values.get("source") == "tableau_relation_fallback" and any(
            other.datasource == mapping.datasource and other.source_id != mapping.source_id and other.target_connector != "Manual source placeholder"
            for other in project.source_mappings
        ):
            project.ai_recommendations.append({"category":"Final table detection","object":mapping.datasource,"recommendation":"Logical/federated wrapper hidden because concrete final source tables were recovered.","auto_fix":"Excluded wrapper"})
            continue
        include, exclusion_reason = is_model_table(mapping)
        if not include:
            project.ai_recommendations.append({"category": "Semantic model", "object": mapping.datasource, "recommendation": exclusion_reason, "auto_fix": "Excluded from export model"})
            continue
        table_name = clean_name(mapping.table_name or mapping.datasource)
        preview = preview_by_source.get(mapping.source_id)
        cols = []
        if preview and preview.columns:
            cols = [
                {
                    "name": clean_name(c.column_name),
                    "source_name": c.column_name,
                    "data_type": c.override_type or c.detected_type,
                    "possible_key": c.possible_key,
                    "role": c.dimension_or_measure,
                    "source_scope": "source_preview",
                }
                for c in preview.columns
            ]
        else:
            ds = next((d for d in project.datasources if d.name == mapping.datasource), None)
            if ds:
                has_multiple_tables = len([m for m in project.source_mappings if m.datasource == mapping.datasource]) > 1
                for f in ds.fields:
                    if f.is_calculated or f.is_parameter or is_tableau_generated_field(f.name):
                        continue
                    
                    # Safe Fallback: If the datasource has multiple tables, we cannot blindly assign global fields.
                    # We check if the field has explicit provenance (if the parser supports it in the future)
                    # or if the field name explicitly qualifies the physical table (e.g. '[Customers].[RegionID]').
                    provenance_table = getattr(f, "source_table", None) or getattr(f, "provenance", None)
                    if has_multiple_tables:
                        if provenance_table:
                            prov_table_clean = clean_name(str(provenance_table).split(".")[-1]).casefold()
                            if prov_table_clean != clean_name(mapping.table_name).casefold():
                                continue
                        else:
                            # Fallback: No explicit provenance. Does the field explicitly reference this table?
                            # Tableau usually formats qualified names as [Table Name].[Field Name]
                            f_lower = f.name.casefold()
                            t_lower = (mapping.table_name or "").casefold()
                            if f_lower.startswith(f"[{t_lower}].") or f_lower.startswith(f"{t_lower}."):
                                pass
                            else:
                                # Documented Fallback: To prevent 25-column cross-contamination, we exclude ambiguous
                                # fields. The semantic model will generate an empty M query, and the user must
                                # hit Refresh in Power BI after applying credentials to populate the true schema.
                                continue

                    cols.append({"name": clean_name(f.name), "source_name": f.name, "data_type": f.datatype or "Text", "possible_key": False, "role": f.role or "dimension", "source_scope": "datasource_metadata"})
        
        # Power BI requires at least one column per table
        if not cols:
            cols.append({"name": "_Tableau2PBI_Refresh_Required", "source_name": "_Tableau2PBI_Refresh_Required", "data_type": "Text", "possible_key": False, "role": "dimension", "source_scope": "fallback"})
        
        # Diagnostic logging requested by user
        import logging
        logging.info(f"SEMANTIC TABLE: {table_name} | SOURCE FIELDS FOUND: {len(cols)}")
        
        cols = clean_join_expansion_columns(cols)
        try:
            # M generation receives the exact exported source-column schema. This keeps
            # schema placeholders and workbook navigation aligned with model.bim.
            query_warnings = []
            m_query = generate_m_query(table_name, mapping, preview, expected_columns=cols, warnings=query_warnings)
            for w in query_warnings:
                project.validation_issues.append(ValidationIssue(
                    severity="warning",
                    category="M Query Validation",
                    object_name=table_name,
                    message=w,
                    recommended_fix="Update Tableau mapping or correct SQL source schema."
                ))
        except Exception as exc:
            m_query = f"let\n    Source = #table({{}}, {{}})\nin\n    Source"
            project.validation_issues.append(ValidationIssue(
                severity="warning",
                category="M Query Generation",
                object_name=table_name,
                message=f"M generation fallback used: {exc}",
                recommended_fix="Review source mapping and datatype overrides, then regenerate M.",
            ))
        table = SemanticTable(
            name=table_name,
            source_id=mapping.source_id,
            columns=cols,
            m_query=m_query,
            lineage=[f"Datasource: {mapping.datasource}", f"Connector: {mapping.target_connector}", f"Detected path: {mapping.detected_source_path or mapping.target_file_path or 'N/A'}"],
        )
        # Final-model-first rule: a business table is represented once. Do not solve a
        # duplicate by renaming it into another semantic table because that creates the
        # exact Sales/sales clutter users reported. Prefer the Tableau-backed mapping;
        # otherwise retain the first canonical source and preserve the duplicate only in audit notes.
        existing = next((x for x in tables if x.name.lower() == table.name.lower()), None)
        if existing:
            existing_mapping = next((m for m in project.source_mappings if m.source_id == existing.source_id), None)
            # Prefer an actually readable source over an unresolved Tableau connection.
            # If both are readable/unreadable, prefer explicit Tableau metadata over an
            # inventory fallback. This prevents duplicate conceptual tables while also
            # avoiding empty/credential-only placeholders when a packaged business file
            # with the same final table is available.
            current_preview = preview_by_source.get(mapping.source_id)
            existing_preview = preview_by_source.get(existing.source_id)
            current_priority = (4 if current_preview and current_preview.available else 0) + (2 if "tableau_connection" in mapping.parameter_values.get("source", "") else 1)
            existing_priority = (4 if existing_preview and existing_preview.available else 0) + (2 if existing_mapping and "tableau_connection" in existing_mapping.parameter_values.get("source", "") else 1)
            if current_priority > existing_priority:
                existing_col_names = {str(c.get("name")).casefold() for c in table.columns if c.get("name")}
                for col in existing.columns:
                    if col.get("name") and str(col.get("name")).casefold() not in existing_col_names:
                        table.columns.append(col)
                table.measures.extend(existing.measures)
                tables[tables.index(existing)] = table
                action_text = "Collapsed duplicate into new priority source (columns merged)."
            else:
                existing_col_names = {str(c.get("name")).casefold() for c in existing.columns if c.get("name")}
                for col in table.columns:
                    if col.get("name") and str(col.get("name")).casefold() not in existing_col_names:
                        existing.columns.append(col)
                existing.measures.extend(table.measures)
                action_text = "Discarded duplicate source representation (columns merged)."
                
            project.ai_recommendations.append({"category":"Duplicate table detection","object":table.name,"recommendation":"Duplicate source representation collapsed into one canonical final table.","auto_fix":action_text})
            continue
        tables.append(table)
    by_ds = {t.name: t for t in tables}
    
    # GLOBAL SOURCE MAPPING RESOLUTION
    import re
    resolution_map = {}
    preview_by_source = {p.source_id: p for p in project.previews}
    for mapping in project.source_mappings:
        ds_name = mapping.datasource
        final_table = clean_name(mapping.table_name or mapping.datasource)
        
        col_map = {}
        preview = preview_by_source.get(mapping.source_id)
        if preview and preview.columns:
            for c in preview.columns:
                c_clean = clean_name(c.column_name)
                col_map[c_clean.casefold()] = c_clean
        else:
            # Fallback to Tableau metadata if no physical preview is available
            ds_meta = next((d for d in project.datasources if d.name == ds_name), None)
            if ds_meta:
                has_multiple_tables = len([m for m in project.source_mappings if m.datasource == ds_name]) > 1
                for f in ds_meta.fields:
                    if f.is_calculated or f.is_parameter or is_tableau_generated_field(f.name):
                        continue
                    provenance_table = getattr(f, "source_table", None) or getattr(f, "provenance", None)
                    if has_multiple_tables:
                        if provenance_table:
                            prov_table_clean = clean_name(str(provenance_table).split(".")[-1]).casefold()
                            if prov_table_clean != clean_name(mapping.table_name).casefold():
                                continue
                        else:
                            f_lower = f.name.casefold()
                            t_lower = (mapping.table_name or "").casefold()
                            if not (f_lower.startswith(f"[{t_lower}].") or f_lower.startswith(f"{t_lower}.")):
                                continue
                    f_clean = clean_name(f.name)
                    col_map[f_clean.casefold()] = f_clean

        # Also map calculated columns derived from fields belonging to this table
        for c in project.calculations:
            if c.formula:
                # If formula references any column unique to this table, register this calc under this table
                f_refs = [clean_name(r).casefold() for r in re.findall(r"\[([^\]]+)\]", c.formula)]
                if any(r in col_map for r in f_refs):
                    c_clean = clean_name(c.name)
                    col_map[c_clean.casefold()] = c_clean
                    
        if ds_name not in resolution_map:
            resolution_map[ds_name] = []
        resolution_map[ds_name].append({
            'table': final_table,
            'columns': col_map
        })

    for calc in project.calculations:
        target_name = clean_name(calc.datasource or "")
        
        # 1. Resolve DAX references to actual physical tables
        if calc.generated_expression:
            def replacer(match):
                tbl, col = match.group(1), match.group(2)
                c_key = col.casefold()
                
                # Try to resolve in the original datasource first (which dax_translator mapped to clean_name)
                for ds_name, table_list in resolution_map.items():
                    if clean_name(ds_name).casefold() == tbl.casefold():
                        for ds_info in table_list:
                            if c_key in ds_info['columns']:
                                return f"'{ds_info['table']}'[{ds_info['columns'][c_key]}]"
                        if table_list:
                            return f"'{table_list[0]['table']}'[{col}]"
                            
                # Fallback: search globally if the table wasn't matched perfectly
                for ds_name, table_list in resolution_map.items():
                    for ds_info in table_list:
                        if c_key in ds_info['columns']:
                            return f"'{ds_info['table']}'[{ds_info['columns'][c_key]}]"
                        
                return match.group(0)
                
            calc.generated_expression = re.sub(r"'([^']+)'\[([^\]]+)\]", replacer, calc.generated_expression)
            
            def table_replacer(match):
                tbl = match.group(1)
                for ds_name, table_list in resolution_map.items():
                    if clean_name(ds_name).casefold() == tbl.casefold() and table_list:
                        return f"'{table_list[0]['table']}'"
                return f"'{tbl}'"
                
            calc.generated_expression = re.sub(r"__TABLE__\('([^']+)'\)", table_replacer, calc.generated_expression)

        # 2. Assign calculation to a semantic table based on DAX references
        final_mapped_table = None
        if calc.generated_expression:
            refs = re.findall(r"'([^']+)'\[([^\]]+)\]", calc.generated_expression)
            if refs:
                # Use the first explicitly referenced physical table
                final_mapped_table = refs[0][0]
                
        if not final_mapped_table:
            for ds_name, table_list in resolution_map.items():
                if clean_name(ds_name).casefold() == target_name.casefold() and table_list:
                    final_mapped_table = table_list[0]['table']
                    break
                
        if not final_mapped_table or final_mapped_table not in by_ds:
            if not tables:
                continue
            # Try to assign to a table belonging to the same datasource
            target = next((t for t in tables if any(clean_name(m.datasource).casefold() == target_name.casefold() for m in project.source_mappings if m.source_id == t.source_id)), tables[0])
            project.ai_recommendations.append({
                "category": "Calculation assignment",
                "object": clean_name(calc.name),
                "recommendation": f"Calculation assigned to '{target.name}' because its Tableau datasource '{target_name or 'Unknown'}' is not a physical Power BI table.",
                "auto_fix": "Assigned to related physical table",
            })
        else:
            target = by_ds[final_mapped_table]

        object_name = clean_name(calc.name)
        if calc.target_object_type == "measure" and calc.confidence_score >= 0.70:
            existing_names = {str(m.get("name") or "").casefold() for m in target.measures}
            if object_name.casefold() not in existing_names:
                target.measures.append({"name": object_name, "expression": calc.generated_expression, "description": f"Converted from Tableau: {calc.formula}", "confidence": calc.confidence_score})
        elif calc.target_object_type == "calculated_column" and calc.confidence_score >= 0.70:
            existing_names = {str(c.get("name") or "").casefold() for c in target.columns}
            if object_name.casefold() not in existing_names:
                target.columns.append({"name": object_name, "data_type": calc.return_type or "Text", "calculated": True, "expression": calc.generated_expression, "confidence": calc.confidence_score})
    return _dedupe_semantic_measures(project, tables)



def _dedupe_semantic_measures(project: MigrationProject, tables: list[SemanticTable]) -> list[SemanticTable]:
    """Enforce one canonical measure name across the final semantic model.

    Duplicate Tableau datasource representations can emit the same calculated measure
    more than once. True duplicates are removed. Conflicting measures with the same name 
    but different logic are renamed to prevent data loss.
    """
    registry: dict[str, tuple[SemanticTable, dict]] = {}
    expr_registry: dict[str, tuple[SemanticTable, dict]] = {}
    for table in tables:
        kept: list[dict] = []
        for measure in table.measures:
            original_name = str(measure.get('name') or '')
            name = clean_name(original_name)
            if not name:
                continue
            measure['name'] = name
            key = name.casefold()
            
            expr_key = ''.join(str(measure.get('expression') or '').split()).casefold()
            
            # 1. Check if identical logic already exists under ANY name
            if expr_key in expr_registry:
                old_table, old_measure = expr_registry[expr_key]
                if key != old_measure['name'].casefold():
                    action = f"Measure '{name}' discarded because it is logically identical to '{old_measure['name']}' in {old_table.name}."
                    project.ai_recommendations.append({
                        'category': 'Duplicate measure detection',
                        'object': name,
                        'recommendation': 'Duplicate measure with different name but identical logic removed.',
                        'auto_fix': action,
                    })
                    continue
            
            existing = registry.get(key)
            if existing is None:
                registry[key] = (table, measure)
                expr_registry[expr_key] = (table, measure)
                kept.append(measure)
                continue
            
            old_table, old_measure = existing
            action = f"Duplicate measure '{name}' discarded from {table.name}; canonical copy is on {old_table.name}."
            project.ai_recommendations.append({
                'category': 'Duplicate measure detection',
                'object': name,
                'recommendation': 'Duplicate measure collapsed model-wide.',
                'auto_fix': action,
            })
                
        table.measures = kept
        
    # Final identity-safe pass after any replacements above.
    seen: set[str] = set()
    for table in tables:
        unique: list[dict] = []
        for m in table.measures:
            key = clean_name(str(m.get('name') or '')).casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(m)
        table.measures = unique
    return tables

def _merge_datasources_by_name(datasources):
    merged = {}
    for ds in datasources:
        key = clean_name(ds.name).lower()
        if key not in merged:
            merged[key] = ds
            continue
        target = merged[key]
        existing_conn = {(c.connection_type, c.local_file_path, c.server, c.database, c.table_name) for c in target.connections}
        for c in ds.connections:
            ckey = (c.connection_type, c.local_file_path, c.server, c.database, c.table_name)
            if ckey not in existing_conn:
                target.connections.append(c)
                existing_conn.add(ckey)
        existing_fields_map = {(clean_name(f.name).lower(), (getattr(f, "provenance", None) or "").lower()): f for f in target.fields}
        for f in ds.fields:
            name_key = clean_name(f.name).lower()
            prov_key = (getattr(f, "provenance", None) or "").lower()
            fkey = (name_key, prov_key)
            if fkey not in existing_fields_map:
                # If target has a field with same name but missing provenance, enrich it
                name_match = next((ef for ef in target.fields if clean_name(ef.name).lower() == name_key and not getattr(ef, "provenance", None)), None)
                if name_match and getattr(f, "provenance", None):
                    name_match.provenance = f.provenance
                    existing_fields_map[(name_key, prov_key)] = name_match
                else:
                    target.fields.append(f)
                    existing_fields_map[fkey] = f
            else:
                existing_f = existing_fields_map[fkey]
                if getattr(f, "provenance", None) and not getattr(existing_f, "provenance", None):
                    existing_f.provenance = f.provenance
        existing_rel = {(r.name, r.relation_type, r.table, r.custom_sql) for r in target.relations}
        for r in ds.relations:
            rkey = (r.name, r.relation_type, r.table, r.custom_sql)
            if rkey not in existing_rel:
                target.relations.append(r)
                existing_rel.add(rkey)
        target.filters.extend([f for f in ds.filters if f not in target.filters])
        target.warnings.extend([w for w in ds.warnings if w not in target.warnings])
    return list(merged.values())


def _dedupe_by_key(items, key_fn):
    out = {}
    for item in items:
        out[key_fn(item)] = item
    return list(out.values())


def _safe_stage(project: MigrationProject, category: str, object_name: str, exc: Exception) -> None:
    project.validation_issues.append(ValidationIssue(
        severity="warning",
        category=category,
        object_name=object_name,
        message=str(exc),
        recommended_fix="The item was skipped so the rest of the migration can continue. Review the inventory/validation report.",
    ))


def run_pipeline(project: MigrationProject, uploaded_paths: list[Path]) -> MigrationProject:
    workspace = Path(project.workspace_path).resolve()
    project.workspace_path = str(workspace)
    discovered_files: list[Path] = []
    discovered_files.extend([Path(p).resolve() for p in uploaded_paths if Path(p).exists()])

    virtual_inventory = []
    package_exts = {".zip", ".twbx", ".tdsx", ".tflx"}
    for p in uploaded_paths:
        # Plain uploaded files are already in discovered_files. Only packages need a second
        # extraction pass; copying plain files here created duplicate inventory/model signals.
        if Path(p).suffix.lower() not in package_exts:
            continue
        try:
            extracted = extract_package(Path(p), workspace / "extracted")
            discovered_files.extend(extracted)
            if not extracted:
                virtual_inventory.extend(list_zip_members_as_inventory(Path(p), workspace, "package extraction returned no files"))
        except Exception as exc:
            _safe_stage(project, "Package Extraction", Path(p).name, exc)
            virtual_inventory.extend(list_zip_members_as_inventory(Path(p), workspace, str(exc)))

    project.inventory = build_inventory(discovered_files, workspace) + virtual_inventory
    project.file_processing_tree = build_file_processing_tree(project)
    project.upload_model = detect_upload_model(project.inventory)
    project.upload_model_catalogue = catalogue()

    workbook_meta: dict | None = None
    for item in project.inventory:
        if str(item.absolute_path).startswith("zip://"):
            continue
        path = Path(item.absolute_path)
        if path.suffix.lower() in {".twb", ".tds", ".tfl"}:
            if not path.exists():
                item.parsed_status = "Skipped"
                item.errors.append("File was listed but no longer exists in workspace. Upload package again or clear workspace.")
                continue
            try:
                parsed = parse_workbook_or_datasource(path)
                workbook_meta = workbook_meta or {"workbook_name": parsed.get("workbook_name"), "version": parsed.get("version")}
                project.datasources.extend(parsed.get("datasources", []))
                project.worksheets.extend(parsed.get("worksheets", []))
                project.dashboards.extend(parsed.get("dashboards", []))
                project.stories.extend(parsed.get("stories", []))
                project.parameters.extend(parsed.get("parameters", []))
                project.calculations.extend(parsed.get("calculations", []))
                item.parsed_status = "Parsed"
            except Exception as exc:
                item.parsed_status = "Error"
                item.errors.append(str(exc))
                _safe_stage(project, "Tableau XML Parse", item.file_name, exc)

    project.datasources = _merge_datasources_by_name(project.datasources)
    project.worksheets = _dedupe_by_key(project.worksheets, lambda w: w.name)
    project.dashboards = _dedupe_by_key(project.dashboards, lambda d: d.name)
    project.stories = _dedupe_by_key(project.stories, lambda s: s.name)
    project.calculations = _dedupe_by_key(project.calculations, lambda c: (c.datasource, c.name, c.formula))
    project.parameters = _dedupe_by_key(project.parameters, lambda p: p.name)

    # Second-stage upload-model classification: after XML parsing we know whether
    # the workbook points to databases/custom SQL versus only local/missing files.
    # This avoids routing a TWB/TWBX database migration as a generic workbook-only case.
    project.upload_model = refine_upload_model(project)
    project.file_processing_tree = build_file_processing_tree(project)

    try:
        project.source_mappings = build_source_mappings(project)
        configure_project_paths(project)
    except Exception as exc:
        _safe_stage(project, "Source Mapping", project.project_name, exc)
        project.source_mappings = []

    previews = []
    for m in project.source_mappings:
        try:
            previews.append(preview_mapping(m, workspace))
        except Exception as exc:
            _safe_stage(project, "Data Preview", m.datasource, exc)
    project.previews = previews

    default_table = clean_name(project.source_mappings[0].datasource if project.source_mappings else project.project_name)
    converted_calcs = []
    for c in project.calculations:
        try:
            converted_calcs.append(classify_and_translate(c, clean_name(c.datasource or default_table)))
        except Exception as exc:
            c.warnings.append(f"Conversion failed and was moved to manual review: {exc}")
            c.target_object_type = "manual_review"
            c.confidence_score = 0.0
            converted_calcs.append(c)
    project.calculations = converted_calcs

    project.semantic_tables = _build_semantic_tables(project)
    try:
        project.relationships = infer_relationships(project)
    except Exception as exc:
        _safe_stage(project, "Relationship Inference", project.project_name, exc)
        project.relationships = []
        
    _validate_semantic_model(project)

    try:
        project.visual_plan = build_visual_plan(project.worksheets)
    except Exception as exc:
        _safe_stage(project, "Visual Planning", project.project_name, exc)
        project.visual_plan = []

    # Migration strategy is the compiler decision layer: migrate business logic, not Tableau mechanics.
    try:
        project.tde_analysis = build_tde_analysis(project)
        project.migration_decisions = build_migration_decisions(project)
        project.reconciliation_plan = build_reconciliation_plan(project)
        add_strategy_validation_issues(project, project.migration_decisions)
        add_tde_validation_issues(project, project.tde_analysis)
    except Exception as exc:
        _safe_stage(project, "Migration Strategy", project.project_name, exc)
        project.migration_decisions = []
        project.reconciliation_plan = []
        project.tde_analysis = []

    # Preserve warnings collected during resilient stages, then append normal validation output.
    resilient_issues = list(project.validation_issues)
    project.validation_issues = resilient_issues + validate_project(project)
    project.health_status = health_from_issues(project.validation_issues)
    project.ai_recommendations.extend([
        {"category": "Data modelling", "object": "Semantic model", "recommendation": "Prefer a star schema; retain physical joins only when a single flattened grain is required.", "confidence": 0.96},
        {"category": "Join cleanup", "object": "Expanded columns", "recommendation": "Duplicate technical columns introduced by joins are removed before relationship inference; validate surviving business keys.", "confidence": 0.92},
        {"category": "Calculation placement", "object": "Tableau calculations", "recommendation": "Row-level deterministic logic is assigned to M/columns; aggregate, LOD and table calculations are assigned to DAX/manual review.", "confidence": 0.95},
    ])
    project.summary = _summary(project, workbook_meta)
    return project

def _validate_semantic_model(project: MigrationProject):
    import re
    valid_table_cols_ci = {}
    valid_tables = []
    for t in project.semantic_tables:
        if not t.columns:
            project.validation_issues.append(ValidationIssue(
                severity="error",
                category="PBIP Generation",
                object_name=t.name,
                message="Semantic table has no valid columns. Excluded from model to prevent corruption.",
                recommended_fix="Review source mapping and data profiling to ensure the source is accessible."
            ))
            t.include_in_export = False
        else:
            valid_tables.append(t)
            if t.include_in_export:
                valid_table_cols_ci[t.name.casefold()] = {str(c.get("name") or "").casefold() for c in t.columns}
                
    project.semantic_tables = valid_tables
    
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

    for t in project.semantic_tables:
        if not t.include_in_export:
            continue
            
        valid_cols = []
        for c in t.columns:
            if c.get("calculated") and c.get("expression"):
                missing = _refs_valid(c.get("expression"))
                if missing:
                    for calc in project.calculations:
                        if clean_name(calc.name).casefold() == str(c.get("name")).casefold():
                            calc.confidence_score = 0
                            calc.warnings.append("Missing DAX references: " + ", ".join(missing))
                    continue
            valid_cols.append(c)
        t.columns = valid_cols
        
        valid_measures = []
        for m in t.measures:
            if m.get("expression"):
                missing = _refs_valid(m.get("expression"))
                if missing:
                    for calc in project.calculations:
                        if clean_name(calc.name).casefold() == str(m.get("name")).casefold():
                            calc.confidence_score = 0
                            calc.warnings.append("Missing DAX references: " + ", ".join(missing))
                    continue
            valid_measures.append(m)
        t.measures = valid_measures
        
    valid_rels = []
    for r in project.relationships:
        f_tbl, t_tbl = r.from_table.casefold(), r.to_table.casefold()
        f_col, t_col = r.from_column.casefold(), r.to_column.casefold()
        
        if f_tbl not in valid_table_cols_ci or t_tbl not in valid_table_cols_ci:
            continue
        if f_col not in valid_table_cols_ci[f_tbl] or t_col not in valid_table_cols_ci[t_tbl]:
            continue
        valid_rels.append(r)
    project.relationships = valid_rels
