import { useEffect, useState } from 'react';
import { Card } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject, SourceMapping } from '../types/project';
import { saveSourceMappings } from '../services/api';

const connectors = ['CSV','Text','Excel','Folder','JSON','XML','Parquet','SQL Server','Oracle','PostgreSQL','MySQL','Snowflake','Databricks','BigQuery','Azure SQL','OData','Web API','SharePoint Folder','OneLake/Fabric Lakehouse','Manual source placeholder'];

export default function Sources({ project, setProject }: {project: MigrationProject; setProject: (p: MigrationProject) => void}) {
  const [mappings, setMappings] = useState<SourceMapping[]>(project.source_mappings);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => setMappings(project.source_mappings), [project.project_id, project.source_mappings]);

  function update(i: number, key: keyof SourceMapping, value: string) {
    const clone = [...mappings]; clone[i] = { ...clone[i], [key]: value }; setMappings(clone);
  }
  async function save() {
    setBusy(true); setError(undefined);
    try { setProject(await saveSourceMappings(project.project_id, mappings)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="page">
    <Card title={`Source Mapping & Connection Update (${mappings.length} sources)`} right={<button className="primary" onClick={save} disabled={busy}>{busy ? 'Saving...' : 'Apply & Regenerate M'}</button>}>
      {error && <div className="error">{error}</div>}
      {!mappings.length && <div className="empty">No sources detected. Re-upload the Tableau ZIP/TWBX/TWB package or review inventory parse errors.</div>}
      <div className="sourceCards">{mappings.map((m, i) => <div className="sourceCard" key={m.source_id}>
        <h3>{m.datasource}</h3><p className="muted">Original: {m.original_connection_type} · Status: {m.mapping_status || 'Detected'}</p>
        <label>Target connector<select value={m.target_connector} onChange={e => update(i, 'target_connector', e.target.value)}>{connectors.map(c => <option key={c}>{c}</option>)}</select></label>
        <label>File path<input value={m.target_file_path || ''} onChange={e => update(i, 'target_file_path', e.target.value)} placeholder="C:\\Data\\source.csv or data/source.csv"/></label>
        <label>Detected source path<input value={m.detected_source_path || ''} onChange={e => update(i, 'detected_source_path', e.target.value)} /></label>
        <label>Server<input value={m.server_name || ''} onChange={e => update(i, 'server_name', e.target.value)}/></label>
        <label>Database<input value={m.database_name || ''} onChange={e => update(i, 'database_name', e.target.value)}/></label>
        <label>Schema<input value={m.schema_name || ''} onChange={e => update(i, 'schema_name', e.target.value)}/></label>
        <label>Table<input value={m.table_name || ''} onChange={e => update(i, 'table_name', e.target.value)}/></label>
        <label>SQL query<textarea value={m.sql_query || ''} onChange={e => update(i, 'sql_query', e.target.value)} /></label>
        <p className="hint">{m.credential_notes}</p>
      </div>)}</div>
    </Card>
    <Card title="TDE / Extract Source-of-Truth Decision">
      <DataTable rows={(project.tde_analysis || []) as Record<string, unknown>[]} empty="No .tde strategy required for this project"/>
    </Card>
  </div>;
}
