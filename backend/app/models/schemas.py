from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

HealthStatus = Literal["Ready", "Ready with warnings", "Blocked", "Manual review required", "Unsupported"]

class FileInventoryItem(BaseModel):
    file_name: str
    extension: str
    folder_path: str = ""
    absolute_path: str
    size_bytes: int
    role: str
    parsed_status: str = "Pending"
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    associated_workbook: str | None = None
    associated_data_source: str | None = None
    associated_extract_or_source: str | None = None

class TableauField(BaseModel):
    name: str
    caption: str | None = None
    datatype: str | None = None
    role: str | None = None
    aggregation: str | None = None
    formula: str | None = None
    is_calculated: bool = False
    is_parameter: bool = False
    datasource: str | None = None
    provenance: str | None = None
    used_in: list[str] = Field(default_factory=list)

class TableauConnection(BaseModel):
    id: str
    datasource: str
    connection_type: str = "Unknown"
    server: str | None = None
    database: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    local_file_path: str | None = None
    custom_sql: str | None = None
    extract_path: str | None = None
    authentication_mode: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

class TableauRelation(BaseModel):
    id: str
    datasource: str
    connection_name: str | None = None
    name: str
    relation_type: str = "table"
    table: str | None = None
    join_type: str | None = None
    left: str | None = None
    right: str | None = None
    clauses: list[dict[str, Any]] = Field(default_factory=list)
    custom_sql: str | None = None
    children: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

class TableauDataSource(BaseModel):
    id: str
    name: str
    caption: str | None = None
    source_kind: str = "Embedded"
    extract_or_live: str = "Unknown"
    connections: list[TableauConnection] = Field(default_factory=list)
    fields: list[TableauField] = Field(default_factory=list)
    relations: list[TableauRelation] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    aliases: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

class TableauWorksheet(BaseModel):
    name: str
    rows: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    marks_type: str | None = None
    filters: list[str] = Field(default_factory=list)
    encodings: dict[str, Any] = Field(default_factory=dict)
    datasource_dependencies: list[str] = Field(default_factory=list)
    fields_used: list[str] = Field(default_factory=list)
    visual_recommendation: str | None = None
    manual_review_notes: list[str] = Field(default_factory=list)

class TableauDashboard(BaseModel):
    name: str
    worksheets: list[str] = Field(default_factory=list)
    objects: list[dict[str, Any]] = Field(default_factory=list)

class TableauStory(BaseModel):
    name: str
    sheets: list[str] = Field(default_factory=list)

class TableauParameter(BaseModel):
    name: str
    datatype: str | None = None
    current_value: Any | None = None
    allowable_values: list[Any] = Field(default_factory=list)
    used_in: list[str] = Field(default_factory=list)
    powerbi_strategy: str = "Disconnected parameter table + SELECTEDVALUE"

class TableauCalculation(BaseModel):
    name: str
    datasource: str | None = None
    formula: str
    return_type: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    used_in: list[str] = Field(default_factory=list)
    classification: str = "Manual review"
    target_object_type: str = "manual_review"
    generated_expression: str | None = None
    confidence_score: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    manual_review_notes: list[str] = Field(default_factory=list)

class SourceMapping(BaseModel):
    source_id: str
    datasource: str
    original_connection_type: str
    detected_source_path: str | None = None
    target_connector: str = "Manual source placeholder"
    target_file_path: str | None = None
    server_name: str | None = None
    database_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    sql_query: str | None = None
    authentication_placeholder: str | None = "Configure in Power BI / gateway"
    gateway_requirement: str | None = None
    privacy_level: str | None = "Organizational"
    import_or_directquery: str = "Import"
    credential_notes: str | None = None
    parameter_values: dict[str, Any] = Field(default_factory=dict)
    mapping_status: str = "Detected"
    powerbi_path_parameter: str | None = None
    resolved_powerbi_path: str | None = None
    path_mode: str = "Unresolved"

class DataProfileColumn(BaseModel):
    column_name: str
    detected_type: str
    override_type: str | None = None
    null_count: int = 0
    distinct_count_estimate: int = 0
    numeric_confidence: float = 0.0
    date_confidence: float = 0.0
    text_confidence: float = 0.0
    possible_key: bool = False
    dimension_or_measure: str = "dimension"
    warnings: list[str] = Field(default_factory=list)

class DataPreview(BaseModel):
    source_id: str
    available: bool
    rows: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[DataProfileColumn] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

class RelationshipCandidate(BaseModel):
    id: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str = "Many-to-one"
    cross_filter_direction: str = "Single"
    active: bool = True
    confidence_score: float = 0.0
    reason: str = ""
    manual_review: bool = False

class SemanticTable(BaseModel):
    name: str
    source_id: str | None = None
    columns: list[dict[str, Any]] = Field(default_factory=list)
    measures: list[dict[str, Any]] = Field(default_factory=list)
    m_query: str | None = None
    lineage: list[str] = Field(default_factory=list)
    include_in_export: bool = True

class ValidationIssue(BaseModel):
    severity: Literal["error", "warning", "info"]
    category: str
    object_name: str
    message: str
    recommended_fix: str | None = None
    auto_fixable: bool = False

class MigrationProject(BaseModel):
    project_id: str
    project_name: str
    workspace_path: str
    inventory: list[FileInventoryItem] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    datasources: list[TableauDataSource] = Field(default_factory=list)
    worksheets: list[TableauWorksheet] = Field(default_factory=list)
    dashboards: list[TableauDashboard] = Field(default_factory=list)
    stories: list[TableauStory] = Field(default_factory=list)
    parameters: list[TableauParameter] = Field(default_factory=list)
    calculations: list[TableauCalculation] = Field(default_factory=list)
    source_mappings: list[SourceMapping] = Field(default_factory=list)
    previews: list[DataPreview] = Field(default_factory=list)
    relationships: list[RelationshipCandidate] = Field(default_factory=list)
    semantic_tables: list[SemanticTable] = Field(default_factory=list)
    visual_plan: list[dict[str, Any]] = Field(default_factory=list)
    migration_decisions: list[dict[str, Any]] = Field(default_factory=list)
    reconciliation_plan: list[dict[str, Any]] = Field(default_factory=list)
    tde_analysis: list[dict[str, Any]] = Field(default_factory=list)
    file_processing_tree: list[dict[str, Any]] = Field(default_factory=list)
    ai_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    upload_model: dict[str, Any] = Field(default_factory=dict)
    upload_model_catalogue: list[dict[str, Any]] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    export_path: str | None = None
    health_status: HealthStatus = "Manual review required"
