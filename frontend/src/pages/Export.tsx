import { useState } from 'react';
import { Download } from 'lucide-react';
import { Card, Badge } from '../components/Cards';
import { MigrationProject } from '../types/project';
import { downloadExportPackage, exportProject } from '../services/api';

export default function ExportPage({ project }: {project: MigrationProject}) {
  const [downloadUrl, setDownloadUrl] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function runExport() {
    setBusy(true);
    setError(undefined);
    setDownloadUrl(undefined);
    try {
      const result = await exportProject(project.project_id);
      const url = result.absolute_download_url || result.download_url;
      setDownloadUrl(url);
      await downloadExportPackage(url, `${project.project_name || 'tableau2pbi'}_PowerBI_Migration_Package.zip`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <div className="page">
    <Card title="PBIP Export Package" right={<Badge tone={project.health_status === 'Blocked' ? 'bad' : 'warn'}>{project.health_status}</Badge>}>
      <p>The export includes a Power BI PBIP safe-mode skeleton, semantic model JSON, Power Query review files, DAX review files, validation report, source mapping file, lineage JSON, TDE extract strategy, reconciliation plan and visual build plan.</p>
      <div className="actions">
        <button className="primary" onClick={runExport} disabled={busy}><Download size={16}/>{busy ? 'Generating and downloading...' : 'Generate Export Package'}</button>
        {downloadUrl && <a className="download" href={downloadUrl} download>Download Package Again</a>}
      </div>
      {error && <div className="error">{error}</div>}
      <div className="note">Safe Openable Mode is default. Unsupported Tableau logic stays in the migration report instead of being written as invalid Power BI artifacts. Legacy .tde files are exported as strategy/validation artifacts, not as refreshable Power BI sources.</div>
    </Card>
  </div>;
}
