import { useState } from 'react';
import { UploadCloud, ShieldAlert, BookOpenCheck } from 'lucide-react';
import { Card, Badge } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject } from '../types/project';
import { loadDemo, uploadProject } from '../services/api';

export default function Upload({ project, setProject, onLoaded }: {project?: MigrationProject; setProject: (p: MigrationProject | undefined) => void; onLoaded: () => void}) {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  async function submit() {
    setBusy(true); setError(undefined); setProject(undefined);
    try { const p = await uploadProject(files); setProject(p); onLoaded(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function demo() {
    setBusy(true); setError(undefined); setProject(undefined);
    try { const p = await loadDemo(); setProject(p); onLoaded(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const inventoryRows = project?.inventory.map(i => ({
    folder_path: i.folder_path, file_name: i.file_name, extension: i.extension, role: i.role,
    status: i.parsed_status, size_bytes: i.size_bytes, associated_workbook: i.associated_workbook || '',
    associated_data_source: i.associated_data_source || '', associated_extract_or_source: i.associated_extract_or_source || '',
    warnings: i.warnings.join('; '), errors: i.errors.join('; ')
  })) || [];

  return <div className="page">
    <Card title="Upload Workspace" right={project ? <Badge tone={project.health_status === 'Blocked' ? 'bad' : 'good'}>{project.project_name}</Badge> : undefined}>
      <div className="uploadGuidance">
        <div><BookOpenCheck size={22}/><b>Upload any supported customer scenario</b><span>TWBX alone, workbook with files, extract with metadata, Prep project, partial package or complete Tableau project.</span></div>
        <div><ShieldAlert size={22}/><b>Do not upload secrets</b><span>Passwords, PAT tokens and private keys must be entered through an approved secure mechanism, never stored in a ZIP.</span></div>
      </div>
      <div className="uploadBox">
        <UploadCloud size={36}/><h3>Select one or more files, or a complete ZIP</h3>
        <p>Supported routing includes .twb, .twbx, .tds, .tdsx, .tfl, .tflx, .hyper, .tde, .csv, .xlsx, .json, .xml, .parquet, .sql and .zip.</p>
        <input type="file" multiple onChange={e => setFiles(Array.from(e.target.files || []))}/>
        {files.length > 0 && <div className="selectedFiles"><b>{files.length} selected:</b> {files.map(f=>f.name).join(', ')}</div>}
        <div className="actions"><button className="primary" disabled={!files.length || busy} onClick={submit}>{busy ? 'Inventorying and classifying...' : 'Upload, Classify & Parse'}</button><button onClick={demo} disabled={busy}>Load Demo Project</button></div>
        {error && <div className="error">{error}</div>}
        <div className="note">After upload, the application opens the Upload Models page and clearly lists the detected scenario, mandatory items, optional evidence, missing information and extraction guidance.</div>
      </div>
    </Card>
    {project && <Card title={`File Inventory - ${project.project_name} (${project.inventory.length} files)`}><DataTable rows={inventoryRows}/></Card>}
  </div>;
}
