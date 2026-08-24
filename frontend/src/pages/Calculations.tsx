import { Card, Badge } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject } from '../types/project';

export default function Calculations({ project }: {project: MigrationProject}) {
  return <div className="page">
    <Card title="Calculation Conversion">
      <DataTable rows={project.calculations.map(c => ({name: c.name, datasource: c.datasource, classification: c.classification, target: c.target_object_type, confidence: c.confidence_score, dependencies: c.dependencies.join(', '), warnings: c.warnings.join('; ')}))}/>
    </Card>
    <div className="calcList">{project.calculations.map(c => <Card key={`${c.datasource}-${c.name}`} title={c.name} right={<Badge tone={c.confidence_score >= 0.8 ? 'good' : c.confidence_score >= 0.6 ? 'warn' : 'bad'}>{Math.round(c.confidence_score * 100)}%</Badge>}>
      <h4>Original Tableau Formula</h4><pre>{c.formula}</pre>
      <h4>Generated DAX / Review Expression</h4><pre>{c.generated_expression || 'Manual review required'}</pre>
      {c.manual_review_notes.map(n => <div className="warn" key={n}>{n}</div>)}
    </Card>)}</div>
  </div>;
}
