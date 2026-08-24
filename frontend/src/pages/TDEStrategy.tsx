import { useEffect, useMemo, useState } from 'react';
import { Badge, Card, Metric } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject, SourceMapping } from '../types/project';
import { saveSourceMappings } from '../services/api';

const connectors = ['CSV','Text','Excel','Folder','JSON','XML','Parquet','SQL Server','Oracle','PostgreSQL','MySQL','Snowflake','Databricks','BigQuery','Azure SQL','OData','Web API','SharePoint Folder','OneLake/Fabric Lakehouse','Manual source placeholder'];
const sections = ['Set original source details', 'Validate recovered source columns', 'TDE scenario and decisions', 'Recovered build logic', 'Extract filter classification', 'Manual review and checkpoints'];

function firstArray(project: MigrationProject, path: string): Record<string, unknown>[] {
  const result: Record<string, unknown>[] = [];
  (project.tde_analysis || []).forEach((row: any) => {
    const val = path.split('.').reduce((acc, key) => acc?.[key], row);
    if (Array.isArray(val)) result.push(...val);
  });
  return result;
}

function isTdeOrExtract(m: SourceMapping) {
  return `${m.original_connection_type} ${m.detected_source_path} ${m.target_file_path} ${m.datasource} ${m.mapping_status}`.toLowerCase().includes('.tde') || `${m.original_connection_type} ${m.detected_source_path} ${m.target_file_path} ${m.datasource} ${m.mapping_status}`.toLowerCase().includes('.hyper') || `${m.mapping_status}`.toLowerCase().includes('legacy tde');
}

function sourceColumnValidationRows(project: MigrationProject) {
  return (project.tde_analysis || []).flatMap((r: any) => (r.source_column_validation || []).map((v: any) => ({ tde_file: r.tde_file, ...v })));
}

function asRows(project: MigrationProject, name: string, sourceRows: Record<string, unknown>[], filterRows: Record<string, unknown>[], tdeRows: Record<string, unknown>[], tdeMappings: SourceMapping[], validationRows: Record<string, unknown>[]) {
  switch (name) {
    case 'Validate recovered source columns':
      return <>
        <div className="note">This validates columns pulled from recovered/original source details against Tableau metadata and calculated-field dependencies. If preview is unavailable, set file/server/table details and save.</div>
        <DataTable rows={validationRows} empty="No column validation rows yet. Save source details or upload readable source files."/>
      </>;
    case 'TDE scenario and decisions':
      return <div className="stackedTables">
        <h3>Detected TDE files</h3><DataTable rows={tdeRows} empty="No .tde files found"/>
        <h3>Scenario classification</h3><DataTable rows={(project.tde_analysis || []).map((r: any) => ({ tde_file: r.tde_file, scenario: r.scenario, priority: r.priority, decision: r.decision, recommended_usage: r.recommended_usage, preferred_architecture: r.preferred_architecture })) as Record<string, unknown>[]} empty="No TDE strategy available"/>
        <h3>TDE/extract mappings kept out of production</h3><DataTable rows={tdeMappings.map(m => ({ source: m.datasource, detected_path: m.detected_source_path, target_path: m.target_file_path, status: m.mapping_status, production_decision: 'Ignore as production source; validation/fallback only' })) as Record<string, unknown>[]} empty="No TDE/extract mappings"/>
      </div>;
    case 'Recovered build logic':
      return <div className="stackedTables">
        <h3>Recovered original/upstream sources</h3><DataTable rows={sourceRows} empty="No original source was recovered yet"/>
        <h3>Recovered TDE build logic</h3><DataTable rows={(project.tde_analysis || []).map((r: any) => ({ tde_file: r.tde_file, recovered_logic: r.recovered_logic, recovered_logic_detail: r.recovered_logic_detail })) as Record<string, unknown>[]} empty="No TDE build logic recovered"/>
      </div>;
    case 'Extract filter classification':
      return <DataTable rows={filterRows} empty="No TDE/extract filters detected"/>;
    case 'Manual review and checkpoints':
      return <DataTable rows={(project.tde_analysis || []).flatMap((r: any) => [
        ...(r.manual_review_required || []).map((x: string) => ({ tde_file: r.tde_file, item: x, category: 'manual review' })),
        ...(r.validation_checkpoints || []).map((x: string) => ({ tde_file: r.tde_file, item: x, category: 'validation checkpoint' })),
        ...(r.omit_rules || []).map((x: string) => ({ tde_file: r.tde_file, item: x, category: 'must not do' })),
      ]) as Record<string, unknown>[]} empty="No TDE manual review items"/>;
    default:
      return null;
  }
}

export default function TDEStrategy({ project, setProject }: {project: MigrationProject; setProject: (p: MigrationProject) => void}) {
  const [mappings, setMappings] = useState<SourceMapping[]>(project.source_mappings || []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [section, setSection] = useState(sections[0]);
  useEffect(() => setMappings(project.source_mappings || []), [project.project_id, project.source_mappings]);

  const detected = (project.tde_analysis || []).length;
  const filterRows = (project.tde_analysis || []).flatMap((r: any) => (r.extract_filter_classification || []).map((f: any) => ({ tde_file: r.tde_file, ...f })));
  const sourceRows = (project.tde_analysis || []).flatMap((r: any) => (r.recovered_sources || []).map((s: any) => ({ tde_file: r.tde_file, ...s })));
  const tdeRows = firstArray(project, 'tde_files');
  const validationRows = sourceColumnValidationRows(project) as Record<string, unknown>[];
  const tdeMappings = mappings.filter(isTdeOrExtract);
  const originalMappings = mappings.filter(m => !isTdeOrExtract(m));
  const editableSources = useMemo(() => originalMappings, [mappings]);

  function update(sourceId: string, key: keyof SourceMapping, value: string) {
    setMappings(mappings.map(m => m.source_id === sourceId ? { ...m, [key]: value } : m));
  }
  function removeSource(sourceId: string) {
    setMappings(mappings.filter(m => m.source_id !== sourceId));
  }
  async function save() {
    setBusy(true); setError(undefined);
    try { setProject(await saveSourceMappings(project.project_id, mappings)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  return <div className="page tdePage">
    <Card title="TDE Source Recovery & Validation" right={<Badge tone={detected ? 'warn' : 'good'}>{detected ? `${detected} TDE strategy item(s)` : 'No TDE detected'}</Badge>}>
      <div className="tdeHeroGrid">
        <div className="tdeRuleBox"><b>Production rule:</b> if a Tableau .tde is used, the application should understand how the TDE was built, recover the upstream source logic, ignore the .tde as the Power BI production source, and use the original sources for the rebuild. The .tde stays as validation baseline or temporary static fallback only.</div>
        <div className="metricsGrid compactMetrics">
          <Metric label="TDE files" value={tdeRows.length}/>
          <Metric label="Recovered sources" value={sourceRows.length}/>
          <Metric label="Editable original sources" value={editableSources.length}/>
          <Metric label="Column validations" value={validationRows.length}/>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
    </Card>

    <Card title="TDE Workbench Section" right={<select className="detailSelect" value={section} onChange={e => setSection(e.target.value)}>{sections.map(s => <option key={s}>{s}</option>)}</select>}>
      {section !== 'Set original source details' && <div className="summaryDetailPanel">{asRows(project, section, sourceRows as Record<string, unknown>[], filterRows as Record<string, unknown>[], tdeRows, tdeMappings, validationRows)}</div>}
      {section === 'Set original source details' && <div>
        <div className="note">Enter or correct the actual source system details that created the TDE. You can also remove unused or unnecessary tables before saving. After saving, the backend regenerates previews, datatype profiles, M queries, semantic model metadata, TDE column validation, and validation issues.</div>
        <div className="actions tdeActions"><button className="primary" onClick={save} disabled={busy}>{busy ? 'Saving & validating...' : 'Save Source Details & Validate Columns'}</button></div>
        {!editableSources.length && <div className="empty">No original source mapping recovered yet. Add source files or provide TWB/TDS/TWBX/TDSX metadata, then re-upload or use manual source placeholder details.</div>}
        <div className="sourceCards twoColCards">{editableSources.map(m => <div className="sourceCard recoveryCard" key={m.source_id}>
          <div className="rowBetween">
            <h3>{m.datasource}{m.table_name ? ` - ${m.table_name}` : (m.detected_source_path ? ` - ${m.detected_source_path.split(/[\\/]/).pop()}` : '')}</h3>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span className="miniStatus">{m.target_connector}</span>
              <button 
                type="button"
                style={{ padding: '2px 8px', fontSize: '11px', background: '#fee2e2', color: '#dc2626', border: '1px solid #f87171', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}
                title="Remove this unused or unnecessary table from the migration model"
                onClick={() => removeSource(m.source_id)}
              >
                ✕ Remove Table
              </button>
            </div>
          </div>
          <p className="muted">Recovered from: {String(m.parameter_values?.source || m.original_connection_type || '')}</p>
          <label>Power BI target connector<select value={m.target_connector} onChange={e => update(m.source_id, 'target_connector', e.target.value)}>{connectors.map(c => <option key={c}>{c}</option>)}</select></label>
          <div className="grid2 tightGrid">
            <label>Power BI readable file path<input value={m.target_file_path || ''} onChange={e => update(m.source_id, 'target_file_path', e.target.value)} placeholder="data/orders_2026.csv or C:\\Data\\orders.csv"/></label>
            <label>Detected source path<input value={m.detected_source_path || ''} onChange={e => update(m.source_id, 'detected_source_path', e.target.value)} /></label>
          </div>
          <div className="grid2 tightGrid">
            <label>Server / host<input value={m.server_name || ''} onChange={e => update(m.source_id, 'server_name', e.target.value)} /></label>
            <label>Database<input value={m.database_name || ''} onChange={e => update(m.source_id, 'database_name', e.target.value)} /></label>
            <label>Schema<input value={m.schema_name || ''} onChange={e => update(m.source_id, 'schema_name', e.target.value)} /></label>
            <label>Table<input value={m.table_name || ''} onChange={e => update(m.source_id, 'table_name', e.target.value)} /></label>
          </div>
          <label>Custom SQL / native query / staging view definition<textarea value={m.sql_query || ''} onChange={e => update(m.source_id, 'sql_query', e.target.value)} placeholder="Paste source SQL if this TDE was built from custom SQL or a staged view" /></label>
          <p className="hint">{m.credential_notes}</p>
        </div>)}</div>
      </div>}
    </Card>
  </div>;
}
