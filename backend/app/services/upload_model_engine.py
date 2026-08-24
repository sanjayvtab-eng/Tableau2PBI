from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable


def model(
    id: str,
    name: str,
    description: str,
    mandatory: str,
    optional: str,
    notes: list[str],
    readiness: str,
    processing_route: list[str],
    next_stage: str,
    production_rule: str,
) -> dict[str, Any]:
    return {
        'id': id,
        'name': name,
        'description': description,
        'mandatory_files': [x.strip() for x in mandatory.split(';') if x.strip()],
        'optional_files': [x.strip() for x in optional.split(';') if x.strip()],
        'extraction_notes': notes,
        'readiness_note': readiness,
        'processing_route': processing_route,
        'next_stage': next_stage,
        'production_rule': production_rule,
    }


MODELS = [
model('complete_project','Complete Tableau Project','Full migration package with workbook metadata and available source assets.','At least one .twb or .twbx','TDS/TDSX; TFL/TFLX; Hyper/TDE; CSV/Excel/JSON/XML/Parquet; SQL; images; documentation',[
'In Tableau Desktop use File > Save As and choose .twbx to package a workbook.',
'Place all related assets under one root folder before compressing the project as ZIP.',
'Do not place passwords, PAT tokens or private keys inside the package.'],'Best automation and lineage coverage.',
['Inventory & package association','Parse workbook/data-source/prep metadata','Map original sources','Preview & validate datatypes','Rebuild joins/unions/relationships','Convert calculations','Validate visuals/model','PBIP export'],
'Source Mapping','Use original/reconnected sources for production; extracts are validation inputs unless explicitly selected.'),
model('twbx_only','Packaged Workbook Only','A .twbx is supplied without separately uploaded source files.','One .twbx','Original source files; connection notes; data dictionary; validation totals',[
'Open the workbook in Tableau Desktop and use File > Save As > Tableau Packaged Workbook (.twbx).',
'Enable inclusion of external files when Tableau provides that option.',
'For external databases, provide connection metadata separately without secrets.'],'Workbook logic can be parsed; source availability depends on package contents.',
['Extract TWBX','Parse TWB metadata','Detect embedded/external connections','Identify missing sources','Collect/confirm source mapping','Continue model conversion'],
'Source Mapping','Do not generate production M for unresolved external sources.'),
model('twbx_sources','Packaged Workbook + Source Files','A .twbx plus local files used by the workbook.','One .twbx; all locally referenced source files that are available','TDS/TDSX; extracts; SQL scripts; mapping documents',[
'Save the workbook as .twbx and copy CSV/Excel/JSON/XML/Parquet files into a Sources folder.',
'Keep original filenames and relative folder structure where possible.',
'Zip the .twbx and Sources folder together.'],'Recommended for file-based Tableau workbooks.',
['Extract TWBX','Associate local source files','Parse workbook metadata','Profile source data','Validate source columns/types','Generate M/model/DAX'],
'Preview & Types','Local source files may be used as production sources after mapping validation.'),
model('twbx_database','Packaged Workbook + Database Details','A .twbx with live or extract database sources and reconnect information.','One .twbx; database platform; server/host; database; schema/table or custom SQL','Port; warehouse; role; gateway notes; refresh rules; non-secret credential instructions',[
'Download or save the workbook as .twbx.',
'In Tableau review Data > Data Source > Edit Connection and record server, database, schema and authentication type.',
'Export custom SQL separately and never include passwords.'],'Supports source reconstruction after connection details are reviewed.',
['Extract TWBX','Parse database/custom SQL metadata','Confirm target connector','Configure secure connection placeholders','Validate source columns','Generate foldable M/native query','Build semantic model'],
'Source Mapping','Database connection metadata is production lineage; credentials remain external/secure.'),
model('twb_only','Workbook Definition Only','An unpackaged Tableau workbook definition without source data.','One .twb','TDS/TDSX; source files; database details; extracts; screenshots',[
'Use Tableau Desktop File > Save As and select Tableau Workbook (.twb).',
'A .twb is XML metadata and normally does not contain source data.',
'Place connection notes beside the .twb when sources cannot be supplied.'],'Good metadata coverage; source mapping is mandatory before production export.',
['Parse TWB XML','Inventory workbook logic','Detect connection metadata','Identify unavailable sources','Configure source mapping','Validate before M generation'],
'Source Mapping','Metadata can drive reconstruction, but unresolved data sources block production export.'),
model('twb_sources','Workbook + Source Files','An unpackaged .twb and its local source files.','One .twb; all locally referenced source files that are available','TDS/TDSX; extracts; SQL; validation totals',[
'Save as .twb and copy referenced files without renaming them.',
'Preserve relative folder structure to improve automatic matching.',
'Zip the workbook and source folders together.'],'Strong option for transparent file-based migration.',
['Parse TWB XML','Associate source files','Profile data','Apply datatype overrides','Rebuild physical preparation','Build relationships/DAX','Validate/export'],
'Preview & Types','Mapped local files can be used for production after validation.'),
model('twb_database','Workbook + Database Details','A .twb plus live database connection and SQL metadata.','One .twb; database platform; server/host; database; schema/table or custom SQL','Port; warehouse; role; gateway; refresh schedule; credential instructions',[
'Save the workbook as .twb.',
'Capture connection metadata from the Tableau Data Source page.',
'Export custom SQL and initial SQL as .sql or .txt.'],'Source validation is required before generating production M.',
['Parse TWB XML','Recover DB/custom SQL lineage','Confirm connector/source mapping','Validate source columns','Generate M/native SQL','Build semantic model/DAX'],
'Source Mapping','Use original database as the Power BI source; do not depend on Tableau extract artifacts.'),
model('datasource_only','Tableau Data Source Only','A TDS/TDSX is supplied without workbook visuals.','One .tds or .tdsx','Source files; extracts; custom SQL; data dictionary',[
'Use Data > data source > Add to Saved Data Sources or save the data source from Tableau.',
'Use .tdsx when local files or extracts must be packaged.',
'Use .tds for XML metadata only.'],'Covers source model, joins and calculations; visuals are unavailable.',
['Extract TDSX if packaged','Parse TDS model/connections','Map original source','Rebuild joins/unions/relationships','Convert datasource calculations','Create semantic model shell'],
'Source Mapping','Generate a semantic/data-model migration; visual conversion remains unavailable without workbook metadata.'),
model('extract_metadata','Extract + Tableau Metadata','A Hyper/TDE extract accompanied by workbook or data-source metadata.','One .hyper or .tde; one associated .twb/.twbx/.tds/.tdsx','Original sources; custom SQL; refresh filters; row-count controls',[
'Locate extracts beside the workbook or in Tableau repository Datasources/Extracts folders.',
'For packaged files, rename a copy of .twbx/.tdsx to .zip and inspect the Data folder.',
'Keep the original package unchanged and upload the extract plus metadata.'],'Good recovery path; the original source remains preferred for production.',
['Parse Tableau metadata','Associate extract to datasource','Recover original source/build logic','Classify extract filters','Configure original source','Validate source columns','Use extract as reconciliation baseline','Generate M/model/DAX from original source'],
'TDE Source Recovery','Extract is validation/fallback; original upstream source is preferred for production.'),
model('extract_only','Extract Only','Only a Hyper or legacy TDE extract is supplied.','One .hyper or .tde','Source system details; TWB/TDS metadata; SQL; refresh rules; expected totals',[
'Hyper files may be found inside packaged workbooks/data sources or Tableau repository folders.',
'TDE is legacy; locate related metadata using the original package or a compatible Tableau version.',
'Provide a source-build note describing joins, filters and refresh logic.'],'Recovery/manual-mapping mode; unsafe production export remains blocked until lineage is supplied.',
['Read extract metadata when supported','Mark original lineage as missing','Request/enter upstream source details','Map required columns','Document unrecoverable logic','Use extract only as static fallback/validation'],
'TDE Source Recovery','Never silently promote TDE to production source. Hyper direct use also requires an explicit migration decision.'),
model('prep_project','Tableau Prep Project','A Tableau Prep flow supplied alone or with workbook/source assets.','One .tfl or .tflx','Input files; output extracts; downstream TWB/TWBX; validation totals',[
'In Tableau Prep Builder use File > Save As and choose .tflx when local inputs can be packaged.',
'Use .tfl for flow metadata only.',
'Include all inputs and representative output samples in the same ZIP.'],'Prep steps can be translated; downstream visual logic requires a workbook.',
['Extract TFLX if packaged','Parse Prep inputs/steps/outputs','Map upstream sources','Translate cleaning/join/union logic','Validate output grain','Generate Power Query/Dataflow plan','Link downstream workbook if supplied'],
'Source Mapping','Prep logic becomes reusable transformation logic; do not treat Prep output alone as full report lineage.'),
model('partial_project','Partial or Missing-Source Project','Some Tableau assets are available but referenced sources are missing.','At least one Tableau metadata file: .twb/.twbx/.tds/.tdsx/.tfl/.tflx','Missing source files; extracts; database details; SQL; screenshots; validation totals',[
'Upload all available assets first; the application will inventory gaps.',
'Obtain missing items from the workbook owner, Tableau repository, packaged workbook, server download or source control.',
'Document unavailable items instead of substituting guessed files.'],'Guided remediation mode; incomplete items remain clearly flagged.',
['Parse all available metadata','Build lineage with confidence labels','Identify mandatory gaps','Collect source mappings/manual evidence','Continue safe conversions only','Block unsafe production export'],
'Source Mapping','Missing lineage remains a manual-review blocker, not an inferred production source.'),
model('server_cloud_export','Tableau Server/Cloud Export Package','Downloaded workbook/data-source packages from Tableau Server or Tableau Cloud.','Downloaded .twbx/.twb and/or .tdsx/.tds','Extracts; source files; site/project inventory; refresh and permission notes',[
'From Tableau Server/Cloud use Download > Tableau Workbook when permitted.',
'Download published data sources separately when they are not embedded.',
'Ask an administrator to enable downloads or export through approved REST API tooling.'],'Processed as exported artifacts; direct server connectivity is not required.',
['Inventory downloaded artifacts','Resolve published datasource references','Parse workbook/datasource metadata','Map original sources','Recover refresh/security notes','Continue standard migration pipeline'],
'Source Mapping','Server/Cloud package is migration evidence; production Power BI should reconnect to approved sources.'),
model('documentation_assisted','Documentation-Assisted Recovery','Tableau assets supplemented by screenshots, specifications or mapping documents.','At least one Tableau artifact or extract','PDF/Word/Excel mapping; screenshots; data dictionary; KPI rules; sign-off totals',[
'Export dashboards as PDF or image from Tableau for visual reference.',
'Export crosstab data as validation evidence, not as replacement lineage.',
'Include functional specifications and calculation definitions where available.'],'Adds migration evidence; documentation alone cannot guarantee executable conversion.',
['Parse executable Tableau artifacts first','Attach documentation as evidence','Use evidence for visual/KPI/manual review','Do not convert undocumented assumptions','Validate with sign-off totals'],
'360 Summary','Documentation augments migration evidence but never overrides executable lineage without review.'),
]
MODEL_BY_ID = {m['id']: m for m in MODELS}


def catalogue() -> list[dict[str, Any]]:
    return MODELS


def _extensions(items: Iterable[Any]) -> set[str]:
    result: set[str] = set()
    for item in items:
        ext = getattr(item, 'extension', None) or Path(getattr(item, 'file_name', '')).suffix
        if ext:
            result.add(ext.lower())
    return result


def _facts(project_or_items: Any) -> dict[str, Any]:
    items = getattr(project_or_items, 'inventory', project_or_items)
    exts = _extensions(items)
    datasources = getattr(project_or_items, 'datasources', []) or []
    connections = [c for ds in datasources for c in getattr(ds, 'connections', [])]
    db_connections = [c for c in connections if any([
        getattr(c, 'server', None), getattr(c, 'database', None), getattr(c, 'schema_name', None),
        getattr(c, 'table_name', None), getattr(c, 'custom_sql', None)
    ]) and not getattr(c, 'local_file_path', None)]
    local_conn = [c for c in connections if getattr(c, 'local_file_path', None)]
    return {
        'exts': exts,
        'has_database_metadata': bool(db_connections),
        'has_local_connection_metadata': bool(local_conn),
        'database_connection_count': len(db_connections),
        'connection_count': len(connections),
    }


def _classify(facts: dict[str, Any]) -> str:
    exts = facts['exts']
    has = lambda *x: any(e in exts for e in x)
    meta = has('.twb','.twbx','.tds','.tdsx','.tfl','.tflx')
    workbook, package_wb = has('.twb','.twbx'), has('.twbx')
    datasource, prep, extract = has('.tds','.tdsx'), has('.tfl','.tflx'), has('.hyper','.tde')
    local_sources = has('.csv','.xlsx','.xls','.json','.xml','.parquet','.txt','.tsv')
    docs, sql = has('.pdf','.doc','.docx','.png','.jpg','.jpeg'), has('.sql')

    # Extract models must take precedence; the extract handling route is materially different.
    if extract and meta:
        return 'extract_metadata'
    if extract and not meta:
        return 'extract_only'
    if workbook and (datasource or prep) and (local_sources or sql):
        return 'complete_project'
    if package_wb and facts.get('has_database_metadata') and not local_sources:
        return 'twbx_database'
    if package_wb and local_sources:
        return 'twbx_sources'
    if package_wb and not local_sources:
        return 'twbx_only'
    if has('.twb') and facts.get('has_database_metadata') and not local_sources:
        return 'twb_database'
    if has('.twb') and local_sources:
        return 'twb_sources'
    if has('.twb') and not local_sources:
        return 'twb_only'
    if datasource and not workbook and not prep:
        return 'datasource_only'
    if prep and not workbook:
        return 'prep_project'
    if docs and meta:
        return 'documentation_assisted'
    if meta:
        return 'partial_project'
    return 'partial_project'


def detect_upload_model(project_or_items: Any) -> dict[str, Any]:
    facts = _facts(project_or_items)
    exts = facts['exts']
    mid = _classify(facts)
    m = MODEL_BY_ID[mid]
    missing: list[str] = []
    blockers: list[str] = []

    if mid in {'twb_only','twbx_only','partial_project'}:
        missing.append('Original source files or complete database connection metadata')
    if mid == 'extract_only':
        missing += ['Associated Tableau metadata', 'Original source lineage and refresh logic']
        blockers.append('Original lineage is not recoverable from the provided files alone')
    if '.tde' in exts:
        missing.append('TDE build logic or original upstream lineage when not recoverable from metadata')
    if mid in {'twb_database','twbx_database'} and not facts.get('has_database_metadata'):
        missing.append('Database server/database/schema/table or custom SQL metadata')
    if not any(x in exts for x in {'.twb','.twbx','.tds','.tdsx','.tfl','.tflx'}):
        blockers.append('No Tableau definition/metadata file was detected')

    confidence = 0.98 if mid in {'complete_project','twbx_sources','twb_sources','extract_metadata'} else 0.90
    if mid in {'twb_database','twbx_database'}:
        confidence = 0.96
    if mid in {'extract_only','partial_project'}:
        confidence = 0.82

    stage_gate = 'Ready' if not blockers and not missing else ('Ready with warnings' if not blockers else 'Manual review required')
    return {
        'model_id': mid,
        'model_name': m['name'],
        **m,
        'detected_extensions': sorted(exts),
        'missing_information': sorted(set(missing)),
        'blocking_gaps': blockers,
        'confidence': confidence,
        'stage_gate': stage_gate,
        'classification_basis': {
            'database_metadata_detected': facts.get('has_database_metadata', False),
            'database_connection_count': facts.get('database_connection_count', 0),
            'connection_count': facts.get('connection_count', 0),
        },
    }


def refine_upload_model(project: Any) -> dict[str, Any]:
    """Reclassify after Tableau XML has been parsed so connection metadata can influence routing."""
    return detect_upload_model(project)
