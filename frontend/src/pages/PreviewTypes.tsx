import { Card } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject } from '../types/project';

export default function PreviewTypes({ project }: {project: MigrationProject}) {
  return <div className="page">
    <Card title="Data Preview & Data Types">
      <p className="muted">The backend generates 10-row previews when data files are available and infers datatypes from source samples or Tableau metadata.</p>
      {project.previews.map(p => <div className="previewBlock" key={p.source_id}>
        <h3>{project.source_mappings.find(m => m.source_id === p.source_id)?.datasource || p.source_id}</h3>
        {p.warnings.map(w => <div className="warn" key={w}>{w}</div>)}
        <h4>Profile</h4><DataTable rows={p.columns as unknown as Record<string, unknown>[]} empty="No profile available"/>
        <h4>10-row Preview</h4><DataTable rows={p.rows} empty="No preview available"/>
      </div>)}
    </Card>
  </div>;
}
