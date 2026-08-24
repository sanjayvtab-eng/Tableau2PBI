from __future__ import annotations
import re
from pathlib import Path
from app.core.name_sanitizer import clean_name

TEMP_MARKERS = ('temp', 'tmp', 'staging', 'stage', 'intermediate', 'helper', 'join_payload', 'union_payload', 'anonymous', 'clipboard', 'parameters')
INTERNAL_MARKERS = ('__tableau', 'tableau_internal', 'metadata record', 'extract metadata', 'measure names', 'measure values')
METADATA_STEMS = ('meta', 'metadata', 'manifest', 'lineage', 'schema', 'validation', 'reconciliation', 'recovery_plan', 'source_recovery', 'config', 'configuration', 'settings', 'catalog', 'inventory', 'project')


def _text(mapping) -> str:
    return ' '.join(str(x or '') for x in [
        mapping.datasource, mapping.table_name, mapping.mapping_status,
        mapping.original_connection_type, mapping.detected_source_path,
        mapping.target_file_path,
    ]).lower()


def is_metadata_artifact_name(value: str | None) -> bool:
    if not value:
        return False
    normalized = str(value).replace('\\','/').lower()
    stem = Path(normalized).stem.lower().replace('.', '_').replace('-', '_')
    tokens = set(re.findall(r'[a-z0-9]+', stem))
    # Strong sidecar patterns only. A business JSON file is not rejected merely because it is JSON.
    if stem.endswith(('_meta', '_metadata', '_manifest', '_lineage', '_schema')):
        return True
    if 'tde_meta' in stem or 'hyper_meta' in stem or 'extract_meta' in stem:
        return True
    if {'validation','plan'}.issubset(tokens) or {'recovery','validation'}.issubset(tokens):
        return True
    return False


def is_model_table(mapping) -> tuple[bool, str]:
    text = _text(mapping)
    if '.tde' in text or 'legacy tde' in text:
        return False, 'Legacy TDE is validation/fallback only.'
    if '.hyper' in text or 'tableau hyper' in text or mapping.mapping_status.lower().startswith('extract'):
        return False, 'Tableau extract artifact is excluded from the production semantic model; recover/map the original source.'
    if is_metadata_artifact_name(mapping.datasource) or is_metadata_artifact_name(mapping.table_name) or is_metadata_artifact_name(mapping.detected_source_path) or is_metadata_artifact_name(mapping.target_file_path):
        return False, 'Metadata/lineage/validation sidecar excluded from the business semantic model.'
    if mapping.target_connector == 'Manual source placeholder' and ('extract' in text or 'dataengine' in text):
        return False, 'Unresolved Tableau extract/internal source excluded from export model.'
    if mapping.target_connector == 'Manual source placeholder' and any(x in text for x in ('federated', 'sqlproxy', 'logical/physical relation metadata')):
        return False, 'Tableau federated/logical wrapper excluded; only recovered physical business sources are modelled.'
    if any(marker in text for marker in INTERNAL_MARKERS):
        return False, 'Tableau internal/generated table excluded from semantic model.'
    tokens = set(re.findall(r'[a-z0-9_]+', text))
    if any(marker in tokens for marker in TEMP_MARKERS):
        return False, 'Temporary/intermediate/join-payload table excluded from semantic model.'
    if mapping.parameter_values.get("source") == "inventory_file" and str(mapping.detected_source_path or "").lower().endswith(".sql"):
        return False, ".sql script files are metadata only; not a business data table."
    if str(mapping.detected_source_path or "").lower().endswith((".sql", ".md")):
        return False, "Script or document artifact excluded from semantic model."
    if str(mapping.parameter_values.get('include_in_model', 'true')).lower() == 'false':
        return False, 'Explicitly excluded from semantic model.'
    return True, 'Final/source-backed model table.'



def is_business_data_inventory_item(item) -> tuple[bool, str]:
    """Classify inventory files for automatic source promotion.

    JSON/XML are supported business sources, but Tableau packages also contain JSON/XML
    metadata, manifests, validation files and application configuration. Those files must
    stay visible in inventory/audit screens without becoming semantic model tables.
    """
    ext = str(getattr(item, 'extension', '') or '').lower()
    if ext in {'.sql', '.md', '.txt', '.sh', '.py'}:
        return False, f'{ext} script/document retained for audit only.'
    if ext not in {'.json', '.xml'}:
        return True, 'Non JSON/XML source candidate.'
    file_name = str(getattr(item, 'file_name', '') or '')
    folder = str(getattr(item, 'folder_path', '') or '').replace('\\', '/').lower()
    role = str(getattr(item, 'role', '') or '').lower()
    full = f"{folder}/{file_name}".lower()
    if 'metadata' in role or is_metadata_artifact_name(file_name) or is_metadata_artifact_name(full):
        return False, 'JSON/XML metadata artifact retained for audit only.'
    parts = {p for p in re.split(r'[/\\]+', folder) if p}
    non_data_dirs = {'metadata','meta','docs','doc','documentation','assets','config','configuration','settings','validation','lineage','reports','report','migration_strategy','manual_review','source_mapping'}
    if parts & non_data_dirs:
        return False, 'JSON/XML is under a metadata/configuration/report folder.'
    business_dirs = {'data','datasource','datasources','source','sources','input','inputs','files'}
    if parts & business_dirs:
        return True, 'JSON/XML is under an explicit business-data folder.'
    # A directly uploaded JSON/XML has no extracted package folder and remains supported.
    if not any(p.startswith(('pkg_', 'n_', 'u_')) for p in parts):
        return True, 'Direct JSON/XML upload is treated as a supported data source.'
    return False, 'Unreferenced JSON/XML inside a Tableau package is audit-only unless Tableau metadata references it.'

def clean_join_expansion_columns(columns: list[dict]) -> list[dict]:
    result, seen = [], set()
    for column in columns:
        name = clean_name(column.get('name') or column.get('source_name') or '')
        source = clean_name(column.get('source_name') or name)
        normalized = name.lower()
        technical_duplicate = normalized.endswith(('_1', '_2', '.1', '.2')) or normalized.startswith(('joined_', 'expanded_'))
        if normalized in seen and technical_duplicate:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        column['name'] = name
        column['source_name'] = source
        result.append(column)
    return result
