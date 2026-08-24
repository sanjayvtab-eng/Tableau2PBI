import { useMemo, useState } from 'react';
import { CheckCircle2, Table2 } from 'lucide-react';
import { Card, Metric, Badge } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject } from '../types/project';

export default function FinalTables({ project }: {project: MigrationProject}) {
  const tables = useMemo(() => project.semantic_tables.filter(t => t.include_in_export), [project.semantic_tables]);
  const [selected, setSelected] = useState(tables[0]?.name || '');
  const table = tables.find(t => t.name === selected) || tables[0];
  return <div className="page finalTablesPage">
    <div className="pageHero compactHero"><div><span className="eyebrow">FINAL POWER BI OUTPUT</span><h1>Final Tables</h1><p>This page intentionally shows only business tables that will be written to the Power BI semantic model. Parsing metadata, extract sidecars and duplicate source representations are excluded.</p></div><Badge tone="good"><CheckCircle2 size={13}/> Export model view</Badge></div>
    <div className="finalTableTabs">{tables.map(t=><button key={t.name} className={selected===t.name?'activeTableTab':''} onClick={()=>setSelected(t.name)}><Table2 size={15}/>{t.name}</button>)}</div>
    {!table ? <Card title="Final tables"><div className="empty">No final business tables are available yet. Complete Source Mapping first.</div></Card> : <Card title={table.name} right={<Badge tone="good">Included in export</Badge>}>
      <div className="summaryKpiGrid modelKpis"><Metric label="Columns" value={table.columns.length}/><Metric label="Measures" value={table.measures.length}/><Metric label="Model status" value="Final"/><Metric label="Source" value={table.source_id || '-'}/></div>
      <details className="cleanDetails"><summary>Lineage & technical details</summary><ul>{table.lineage.map(l=><li key={l}>{l}</li>)}</ul></details>
      <h3>Columns</h3><DataTable rows={table.columns as Record<string, unknown>[]}/>
      {!!table.measures.length && <><h3>Measures</h3><DataTable rows={table.measures as Record<string, unknown>[]}/></>}
    </Card>}
  </div>;
}
