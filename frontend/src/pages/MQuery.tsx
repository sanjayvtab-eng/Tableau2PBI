import { Card } from '../components/Cards';
import { MigrationProject } from '../types/project';

export default function MQuery({ project }: {project: MigrationProject}) {
  return <div className="page">
    {project.semantic_tables.map(t => <Card key={t.name} title={`M Query Review - ${t.name}`} right={<button onClick={() => navigator.clipboard.writeText(t.m_query || '')}>Copy M</button>}>
      <pre className="codeBlock">{t.m_query}</pre>
    </Card>)}
  </div>;
}
