import { Card, Badge } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject } from '../types/project';

export default function Validation({ project }: {project: MigrationProject}) {
  const errors = project.validation_issues.filter(i => i.severity === 'error').length;
  const warnings = project.validation_issues.filter(i => i.severity === 'warning').length;
  const manual = (project.migration_decisions || []).filter(d => d.manual_review).length;
  return <div className="page">
    <Card title="Validation & Auto-Fix Center" right={<><Badge tone={errors ? 'bad' : 'good'}>{errors} errors</Badge><Badge tone={warnings ? 'warn' : 'good'}>{warnings} warnings</Badge><Badge tone={manual ? 'warn' : 'good'}>{manual} manual decisions</Badge></>}>
      <DataTable rows={project.validation_issues as unknown as Record<string, unknown>[]} empty="No validation issues detected"/>
    </Card>
    <Card title="TDE Extract Strategy - TDE is validation/fallback, not source of truth">
      <DataTable rows={(project.tde_analysis || []) as Record<string, unknown>[]} empty="No legacy .tde extract detected"/>
    </Card>
    <Card title="Migration Strategy Decisions - migrate business logic, not Tableau mechanics">
      <DataTable rows={(project.migration_decisions || []) as Record<string, unknown>[]} empty="No migration decisions generated"/>
    </Card>
    <Card title="Accuracy & Reconciliation Plan">
      <DataTable rows={(project.reconciliation_plan || []) as Record<string, unknown>[]} empty="No reconciliation plan generated"/>
    </Card>
  </div>;
}
