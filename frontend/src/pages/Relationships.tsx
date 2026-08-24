import { useMemo, useState } from 'react';
import { Link2, Plus, Save, Table2, ShieldCheck } from 'lucide-react';
import { Card, Badge, Metric } from '../components/Cards';
import { MigrationProject, Relationship } from '../types/project';
import { saveRelationships } from '../services/api';

export default function Relationships({ project, setProject }: {project: MigrationProject; setProject: (p: MigrationProject) => void}) {
  const finalTables = useMemo(() => project.semantic_tables.filter(t => t.include_in_export), [project.semantic_tables]);
  const tableNames = new Set(finalTables.map(t => t.name));
  const initial = project.relationships.filter(r => r.active && !r.manual_review && tableNames.has(r.from_table) && tableNames.has(r.to_table));
  const [rels, setRels] = useState<Relationship[]>(initial);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string>();
  function update(i: number, key: keyof Relationship, value: string | boolean) { const copy = [...rels]; copy[i] = {...copy[i], [key]: value}; setRels(copy); }
  function add() { const id = `manual_${Date.now()}`; setRels([...rels, {id, from_table: '', from_column: '', to_table: '', to_column: '', cardinality: 'Many-to-one', cross_filter_direction: 'Single', active: true, confidence_score: 1, reason: 'User-created final relationship', manual_review: false}]); setEditing(id); }
  async function save() { setBusy(true); try { setProject(await saveRelationships(project.project_id, rels)); } finally { setBusy(false); } }
  const cols = (table: string) => finalTables.find(t => t.name === table)?.columns || [];
  return <div className="page finalModelPage">
    <div className="pageHero compactHero">
      <div><span className="eyebrow">POWER BI SEMANTIC MODEL</span><h1>Final Model & Relationships</h1><p>Only final business tables and relationships that will be used in the Power BI model are shown here. Tableau metadata, extract artifacts, duplicate candidates and rejected relationship guesses are hidden from the normal view.</p></div>
      <div className="heroActions"><button onClick={add}><Plus size={16}/> Add relationship</button><button className="primary" onClick={save} disabled={busy}><Save size={16}/>{busy ? 'Saving...' : 'Save final model'}</button></div>
    </div>
    <div className="summaryKpiGrid modelKpis"><Metric label="Final tables" value={finalTables.length}/><Metric label="Final relationships" value={rels.length}/><Metric label="Filter direction" value="Single"/><Metric label="Ambiguous paths" value="Prevented"/></div>
    <Card title="Final Power BI tables" right={<Badge tone="good"><ShieldCheck size={13}/> Clean model</Badge>}>
      <div className="finalTableStrip">{finalTables.map(t => <div className="finalTablePill" key={t.name}><Table2 size={17}/><div><b>{t.name}</b><span>{t.columns.length} columns · {t.measures.length} measures</span></div></div>)}</div>
    </Card>
    <Card title="Final relationships" right={<span className="muted">One approved relationship per table pair</span>}>
      {!rels.length && <div className="empty friendlyEmpty"><Link2 size={30}/><b>No final relationship was safely inferred.</b><span>Add only the business relationship required by the Power BI model.</span></div>}
      <div className="finalRelationshipList">{rels.map((r, i) => {
        const isEdit = editing === r.id;
        return <div className="finalRelationshipRow" key={r.id}>
          {!isEdit ? <>
            <div className="relationshipFlow"><div><small>Many / From</small><b>{r.from_table}</b><span>{r.from_column}</span></div><div className="relationshipConnector"><span>{r.cardinality}</span><Link2 size={22}/><small>{r.cross_filter_direction} filter</small></div><div><small>One / To</small><b>{r.to_table}</b><span>{r.to_column}</span></div></div>
            <div className="rowActions"><Badge tone="good">Active</Badge><button onClick={() => setEditing(r.id)}>Edit</button><button onClick={() => setRels(rels.filter(x => x.id !== r.id))}>Remove</button></div>
          </> : <div className="relationshipEditGrid">
            <label>From table<select value={r.from_table} onChange={e => update(i,'from_table',e.target.value)}><option value="">Select table</option>{finalTables.map(t=><option key={t.name}>{t.name}</option>)}</select></label>
            <label>From column<select value={r.from_column} onChange={e => update(i,'from_column',e.target.value)}><option value="">Select column</option>{cols(r.from_table).map(c=><option key={String(c.name)}>{String(c.name)}</option>)}</select></label>
            <label>To table<select value={r.to_table} onChange={e => update(i,'to_table',e.target.value)}><option value="">Select table</option>{finalTables.map(t=><option key={t.name}>{t.name}</option>)}</select></label>
            <label>To column<select value={r.to_column} onChange={e => update(i,'to_column',e.target.value)}><option value="">Select column</option>{cols(r.to_table).map(c=><option key={String(c.name)}>{String(c.name)}</option>)}</select></label>
            <label>Cardinality<select value={r.cardinality} onChange={e=>update(i,'cardinality',e.target.value)}><option>Many-to-one</option><option>One-to-one</option></select></label>
            <label>Filter direction<select value={r.cross_filter_direction} onChange={e=>update(i,'cross_filter_direction',e.target.value)}><option>Single</option></select></label>
            <button className="primary" onClick={()=>setEditing(undefined)}>Done</button>
          </div>}
        </div>})}</div>
    </Card>
  </div>;
}
