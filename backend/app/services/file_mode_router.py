from __future__ import annotations
from typing import Any
from app.models.schemas import MigrationProject

MODE_RULES = {
    '.zip': ('Package', 'Extract package → inventory every member → route each child by extension', 'Inventory / Package Association'),
    '.twbx': ('Packaged Workbook', 'Extract → parse TWB XML → associate extracts/local files/assets', 'Workbook & Data Source Parsing'),
    '.tdsx': ('Packaged Data Source', 'Extract → parse TDS XML → recover connections and extract lineage', 'Source Mapping'),
    '.tflx': ('Packaged Prep Flow', 'Extract → parse TFL → recover preparation sequence and outputs', 'Preparation Logic Review'),
    '.twb': ('Workbook Definition', 'Parse workbook XML → sheets/dashboards/stories/data sources/calculations', '360 Summary / Source Mapping'),
    '.tds': ('Data Source Definition', 'Parse data-source XML → connections/model/fields/filters', 'Source Mapping'),
    '.tfl': ('Prep Flow', 'Parse preparation flow → inputs/cleaning/joins/unions/outputs', 'Preparation Logic Review'),
    '.hyper': ('Hyper Extract', 'Read metadata/preview when API is available; prefer original source for production', 'Source Mapping / Validation Baseline'),
    '.tde': ('Legacy TDE', 'Recover upstream logic from Tableau metadata; validation/fallback only', 'TDE Source Recovery'),
    '.csv': ('Tabular Source', 'Profile 10 rows → infer types/keys → generate Power Query source', 'Preview & Types'),
    '.xlsx': ('Tabular Source', 'Inspect sheets → profile 10 rows → infer types/keys', 'Preview & Types'),
    '.xls': ('Tabular Source', 'Inspect sheets → profile 10 rows → infer types/keys', 'Preview & Types'),
    '.json': ('Structured Source', 'Inspect schema → normalize records/lists → profile columns', 'Preview & Types'),
    '.xml': ('Structured Source', 'Inspect nodes → map repeating records → profile columns', 'Preview & Types'),
    '.parquet': ('Columnar Source', 'Read schema/statistics → profile sample → generate connector logic', 'Preview & Types'),
    '.sql': ('SQL Logic', 'Review SQL → classify source-side logic → Value.NativeQuery/view recommendation', 'Source Mapping / M Query'),
    '.pdf': ('Documentation Evidence', 'Inventory as evidence; use for manual validation only', 'Validation / Visual Plan'),
    '.png': ('Visual Asset', 'Preserve as report/reference asset; do not treat as data lineage', 'Visual Plan'),
    '.jpg': ('Visual Asset', 'Preserve as report/reference asset; do not treat as data lineage', 'Visual Plan'),
    '.jpeg': ('Visual Asset', 'Preserve as report/reference asset; do not treat as data lineage', 'Visual Plan'),
}

TDE_REQUIRED_INFORMATION = [
    'Associated TWB/TWBX/TDS/TDSX/TFL/TFLX metadata',
    'Original source type and connection details',
    'Server/database/schema/table or original file paths',
    'Custom SQL, joins, unions, relationships and source filters',
    'Extract filters, aggregation, row limits and incremental-refresh key',
    'Calculated fields, LOD expressions, table calculations, aliases/groups',
    'Expected columns, datatypes, keys, row counts and business totals',
    'Credentials/gateway details supplied securely outside the package',
]


def build_file_processing_tree(project: MigrationProject) -> list[dict[str, Any]]:
    roots: dict[str, dict[str, Any]] = {}
    model = project.upload_model or {}
    model_next = model.get('next_stage', '360 Summary')
    for item in project.inventory:
        ext = item.extension.lower()
        mode, process, next_stage = MODE_RULES.get(ext, ('Manual Review', 'Inventory and classify; do not silently ignore', 'Validation'))
        package = item.folder_path.split('/')[0] if item.folder_path else 'Uploaded files'
        root = roots.setdefault(package, {
            'id': package,
            'label': package,
            'node_type': 'package',
            'detected_model': model.get('model_name'),
            'recommended_project_next_stage': model_next,
            'children': []
        })
        node = {
            'id': f"{package}:{item.folder_path}:{item.file_name}",
            'label': item.file_name,
            'extension': ext,
            'role': item.role,
            'mode': mode,
            'processing_path': process,
            'next_stage': next_stage,
            'used_for': _usage_for_extension(ext),
            'status': item.parsed_status,
            'warnings': item.warnings,
            'errors': item.errors,
            'children': [],
        }
        if ext == '.tde':
            node['production_source_allowed'] = False
            node['recommended_usage'] = 'Validation baseline or temporary static fallback only'
            node['required_information'] = TDE_REQUIRED_INFORMATION
        elif ext == '.hyper':
            node['production_source_allowed'] = False
            node['recommended_usage'] = 'Extract metadata/data validation; prefer recovered original source for production migration'
        root['children'].append(node)
    return list(roots.values())


def _usage_for_extension(ext: str) -> str:
    return {
        '.twb': 'Report definition and migration logic', '.twbx': 'Packaged report definition plus embedded assets',
        '.tds': 'Datasource/model definition', '.tdsx': 'Packaged datasource/model definition',
        '.tfl': 'Preparation/transformation definition', '.tflx': 'Packaged preparation/transformation definition',
        '.tde': 'Legacy validation baseline / fallback snapshot', '.hyper': 'Extract validation baseline / metadata reference',
        '.csv': 'Candidate production source or validation data', '.xlsx': 'Candidate production source or validation data',
        '.xls': 'Candidate production source or validation data', '.json': 'Candidate production source or validation data',
        '.xml': 'Candidate production source or metadata source', '.parquet': 'Candidate production source or validation data',
        '.sql': 'Source-side transformation/custom SQL reconstruction', '.pdf': 'Manual validation/documentation evidence',
        '.png': 'Visual/layout asset', '.jpg': 'Visual/layout asset', '.jpeg': 'Visual/layout asset', '.zip': 'Container only',
    }.get(ext, 'Manual review / supporting evidence')
