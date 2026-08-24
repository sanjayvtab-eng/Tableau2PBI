import { Card } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject } from '../types/project';

export default function VisualPlan({ project }: {project: MigrationProject}) {
  return <div className="page">
    <Card title="Visual Conversion Plan">
      <p className="muted">Safe mode generates a visual build plan. Schema-safe PBIR visual JSON can be added as an experimental extension later.</p>
      <DataTable rows={project.visual_plan as Record<string, unknown>[]} empty="No worksheets detected for visual planning"/>
    </Card>
  </div>;
}
