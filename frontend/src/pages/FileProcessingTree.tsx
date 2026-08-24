import { useState } from 'react';
import { ChevronDown, ChevronRight, FileArchive, FileCode2, Database, AlertTriangle, ArrowRightCircle } from 'lucide-react';
import { Card, Badge } from '../components/Cards';
import { MigrationProject } from '../types/project';

function Node({node, depth=0}: {node:any; depth?:number}) {
  const [open, setOpen] = useState(depth < 1);
  const children = node.children || [];
  return <div className="treeNode" style={{marginLeft: depth * 18}}>
    <button className="treeRow" onClick={() => setOpen(!open)}>
      <span>{children.length ? (open ? <ChevronDown size={16}/> : <ChevronRight size={16}/>) : <span className="treeSpacer"/>}</span>
      {node.node_type === 'package' ? <FileArchive size={18}/> : node.extension === '.tde' || node.extension === '.hyper' ? <Database size={18}/> : <FileCode2 size={18}/>} 
      <b>{node.label}</b><span className="treeMode">{node.mode || node.node_type}</span><Badge tone={node.errors?.length ? 'bad' : node.warnings?.length ? 'warn' : 'good'}>{node.status || 'Detected'}</Badge>
    </button>
    {open && node.node_type === 'package' && <div className="treeDetail projectRoute"><b>Detected project model:</b> {node.detected_model || 'Pending'}<br/><b>Project next stage:</b> {node.recommended_project_next_stage || '360 Summary'}</div>}
    {open && node.processing_path && <div className="treeDetail">
      <div><b>Processing route:</b> {node.processing_path}</div>
      <div className="treeNext"><ArrowRightCircle size={15}/><b>Use this processed file next in:</b> {node.next_stage}</div>
      <div><b>Purpose in migration:</b> {node.used_for}</div>
      {node.extension === '.tde' && <><div className="tdeTreeRule"><AlertTriangle size={16}/> TDE is not a production source. Recover its original source and use TDE only for validation/fallback.</div><b>Required supporting information</b><ul>{(node.required_information || []).map((x:string) => <li key={x}>{x}</li>)}</ul></>}
      {node.extension === '.hyper' && <div className="tdeTreeRule"><AlertTriangle size={16}/> Hyper is treated as extract evidence/validation by default; use the recovered original source for production when available.</div>}
    </div>}
    {open && children.map((c:any) => <Node key={c.id} node={c} depth={depth+1}/>)}
  </div>
}
export default function FileProcessingTree({project}:{project:MigrationProject}) {
 return <div className="page"><Card title="File Processing & Next-Stage Routing" right={<Badge tone="neutral">{project.inventory.length} inventoried files</Badge>}>
   <div className="note">Every uploaded file is assigned a processing mode, a migration purpose, and the application screen where its processed output should be used next. Packages are expanded first; child files are then routed independently.</div>
   <div className="treePanel">{(project.file_processing_tree || []).map((n:any) => <Node key={n.id} node={n}/>)}</div>
 </Card></div>;
}
