export type ValidationIssue = {
  severity: 'error' | 'warning' | 'info';
  category: string;
  object_name: string;
  message: string;
  recommended_fix?: string;
  auto_fixable: boolean;
};

export type FileInventoryItem = {
  file_name: string;
  extension: string;
  folder_path: string;
  absolute_path: string;
  size_bytes: number;
  role: string;
  parsed_status: string;
  errors: string[];
  warnings: string[];
  associated_workbook?: string;
  associated_data_source?: string;
  associated_extract_or_source?: string;
};

export type SourceMapping = {
  source_id: string;
  datasource: string;
  original_connection_type: string;
  detected_source_path?: string;
  target_connector: string;
  target_file_path?: string;
  server_name?: string;
  database_name?: string;
  schema_name?: string;
  table_name?: string;
  sql_query?: string;
  authentication_placeholder?: string;
  gateway_requirement?: string;
  privacy_level?: string;
  import_or_directquery: string;
  credential_notes?: string;
  parameter_values: Record<string, unknown>;
  mapping_status: string;
  powerbi_path_parameter?: string;
  resolved_powerbi_path?: string;
  path_mode?: string;
};

export type DataPreview = {
  source_id: string;
  available: boolean;
  rows: Record<string, unknown>[];
  columns: Array<{
    column_name: string;
    detected_type: string;
    override_type?: string;
    null_count: number;
    distinct_count_estimate: number;
    numeric_confidence: number;
    date_confidence: number;
    text_confidence: number;
    possible_key: boolean;
    dimension_or_measure: string;
    warnings: string[];
  }>;
  warnings: string[];
};

export type Calculation = {
  name: string;
  datasource?: string;
  formula: string;
  return_type?: string;
  dependencies: string[];
  used_in: string[];
  classification: string;
  target_object_type: string;
  generated_expression?: string;
  confidence_score: number;
  warnings: string[];
  manual_review_notes: string[];
};

export type Relationship = {
  id: string;
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  cardinality: string;
  cross_filter_direction: string;
  active: boolean;
  confidence_score: number;
  reason: string;
  manual_review: boolean;
};

export type SemanticTable = {
  name: string;
  source_id?: string;
  columns: Array<Record<string, unknown>>;
  measures: Array<Record<string, unknown>>;
  m_query?: string;
  lineage: string[];
  include_in_export: boolean;
};


export type UploadModelDefinition = {
  id: string;
  name: string;
  description: string;
  mandatory_files: string[];
  optional_files: string[];
  extraction_notes: string[];
  readiness_note: string;
  processing_route: string[];
  next_stage: string;
  production_rule: string;
};

export type DetectedUploadModel = UploadModelDefinition & {
  model_id: string;
  model_name: string;
  detected_extensions: string[];
  missing_information: string[];
  confidence: number;
  blocking_gaps: string[];
  stage_gate: string;
  classification_basis: Record<string, unknown>;
};

export type MigrationProject = {
  project_id: string;
  project_name: string;
  workspace_path: string;
  inventory: FileInventoryItem[];
  summary: Record<string, unknown>;
  datasources: Array<any>;
  worksheets: Array<any>;
  dashboards: Array<any>;
  stories: Array<any>;
  parameters: Array<any>;
  calculations: Calculation[];
  source_mappings: SourceMapping[];
  previews: DataPreview[];
  relationships: Relationship[];
  semantic_tables: SemanticTable[];
  visual_plan: Array<any>;
  migration_decisions: Array<Record<string, unknown>>;
  reconciliation_plan: Array<Record<string, unknown>>;
  tde_analysis: Array<Record<string, unknown>>;
  file_processing_tree: Array<Record<string, unknown>>;
  ai_recommendations: Array<Record<string, unknown>>;
  upload_model: DetectedUploadModel;
  upload_model_catalogue: UploadModelDefinition[];
  validation_issues: ValidationIssue[];
  export_path?: string;
  health_status: string;
};
