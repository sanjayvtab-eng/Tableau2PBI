import { Badge, Card, Metric } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject } from '../types/project';

function connectorCounts(project: MigrationProject) {
  const counts: Record<string, number> = {};
  for (const s of project.source_mappings || []) counts[s.target_connector || 'Unknown'] = (counts[s.target_connector || 'Unknown'] || 0) + 1;
  return Object.entries(counts).map(([connector, count]) => ({ connector, count }));
}

function sourceRows(project: MigrationProject): Record<string, unknown>[] {
  return (project.source_mappings || []).map(s => ({
    source: s.datasource,
    original_type: s.original_connection_type,
    target_connector: s.target_connector,
    status: s.mapping_status,
    detected_path: s.detected_source_path,
    target_path: s.target_file_path,
    table: s.table_name,
    directquery_import: s.import_or_directquery,
    notes: s.credential_notes,
  }));
}

function extractRows(project: MigrationProject): Record<string, unknown>[] {
  return (project.source_mappings || [])
    .filter(s => `${s.original_connection_type} ${s.detected_source_path} ${s.target_file_path} ${s.mapping_status}`.toLowerCase().includes('extract') || `${s.detected_source_path} ${s.target_file_path}`.toLowerCase().includes('.tde') || `${s.detected_source_path} ${s.target_file_path}`.toLowerCase().includes('.hyper'))
    .map(s => ({
      source: s.datasource,
      extract_or_tde: s.detected_source_path || s.target_file_path,
      status: s.mapping_status,
      production_decision: s.mapping_status?.toLowerCase().includes('tde') ? 'Ignore for production; use original source instead' : 'Review extract vs original source',
      credential_notes: s.credential_notes,
    }));
}

export default function SourceOverview({ project }: {project: MigrationProject}) {
  const manual = (project.source_mappings || []).filter(s => s.target_connector === 'Manual source placeholder').length;
  const local = (project.source_mappings || []).filter(s => ['CSV','Text','Excel','JSON','XML','Parquet'].includes(s.target_connector)).length;
  const tde = (project.source_mappings || []).filter(s => `${s.detected_source_path} ${s.target_file_path} ${s.mapping_status}`.toLowerCase().includes('.tde') || `${s.mapping_status}`.toLowerCase().includes('tde')).length;
  return <div className="page">
    <Card title="Source Overview & Migration Decision" right={<Badge tone={manual ? 'warn' : 'good'}>{manual ? `${manual} source(s) need review` : 'All sources mapped'}</Badge>}>
      <div className="metricsGrid">
        <Metric label="Detected source mappings" value={project.source_mappings?.length || 0}/>
        <Metric label="Local readable files" value={local}/>
        <Metric label="Legacy TDE / extracts" value={tde}/>
        <Metric label="Manual source placeholders" value={manual}/>
      </div>
      <div className="note">
        This page is read-only. Use <b>Source Mapping</b> to edit connection details and <b>TDE Source Recovery</b> when a .tde is present. Tableau .tde files are treated as legacy validation baselines, not Power BI production sources.
      </div>
    </Card>
    <div className="grid2">
      <Card title="Connector distribution"><DataTable rows={connectorCounts(project)} empty="No connector decisions yet"/></Card>
      <Card title="Extract/TDE production decision"><DataTable rows={extractRows(project)} empty="No extract or TDE source detected"/></Card>
    </div>
    <Card title="Source inventory summary">
      <DataTable rows={sourceRows(project)} empty="No sources detected"/>
    </Card>
  </div>;
}
