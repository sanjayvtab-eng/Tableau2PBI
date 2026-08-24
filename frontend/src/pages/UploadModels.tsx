import { ArrowRight, CheckCircle2, CircleHelp, FileArchive, Info, Route, ShieldCheck, AlertTriangle } from 'lucide-react';
import { Card, Badge } from '../components/Cards';
import { MigrationProject, UploadModelDefinition } from '../types/project';

function ModelCard({ model, detected }: { model: UploadModelDefinition; detected: boolean }) {
  return <div className={`modelCard ${detected ? 'detectedModel' : ''}`}>
    <div className="modelHeader">
      <div><h3>{model.name}</h3><p>{model.description}</p></div>
      {detected && <Badge tone="good">Detected</Badge>}
    </div>
    <div className="modelColumns">
      <section><h4><CheckCircle2 size={16}/> Mandatory</h4>{model.mandatory_files.map((x,i)=><div className="requirementRow" key={i}>{x}</div>)}</section>
      <section><h4><CircleHelp size={16}/> Optional / Recommended</h4>{model.optional_files.map((x,i)=><div className="requirementRow optional" key={i}>{x}</div>)}</section>
    </div>
    <div className="modelRoute"><Route size={16}/><div><b>Processing route</b><div className="routeSteps">{model.processing_route.map((x,i)=><span key={x}>{i>0 && <ArrowRight size={13}/>}<em>{x}</em></span>)}</div><div className="nextStage"><b>Next application stage:</b> {model.next_stage}</div></div></div>
    <details><summary><FileArchive size={16}/> How to obtain or extract these files</summary>
      <ol>{model.extraction_notes.map((x,i)=><li key={i}>{x}</li>)}</ol>
    </details>
    <div className="productionRule"><ShieldCheck size={15}/><span><b>Production rule:</b> {model.production_rule}</span></div>
    <div className="readinessNote"><Info size={15}/>{model.readiness_note}</div>
  </div>
}

export default function UploadModels({ project }: { project?: MigrationProject }) {
  const models = project?.upload_model_catalogue || [];
  const detected = project?.upload_model;
  return <div className="page">
    <Card title="Detected Upload Model & Processing Route" right={detected?.model_name ? <Badge tone={detected.blocking_gaps?.length ? 'warn' : 'good'}>{detected.stage_gate || detected.model_name}</Badge> : undefined}>
      <p className="lead">The application first classifies the uploaded Tableau assets, then routes them through the correct migration path. Classification is refined after Tableau XML is parsed, so database-backed workbooks are distinguished from workbook-only or file-source models.</p>
      {detected?.model_name && <>
        <div className="detectedPanel">
          <div><b>Detected model</b><h2>{detected.model_name}</h2><p>{detected.description}</p></div>
          <div><b>Confidence</b><h2>{Math.round((detected.confidence || 0) * 100)}%</h2><p>{detected.readiness_note}</p></div>
          <div><b>Detected extensions</b><p>{(detected.detected_extensions || []).join(', ') || 'None'}</p></div>
          <div><b>Next application stage</b><h2 className="nextStageHeadline">{detected.next_stage}</h2><p>{detected.production_rule}</p></div>
        </div>
        <div className="detectedRoutePanel"><Route size={19}/><div><b>Recommended processing route</b><div className="routeSteps large">{(detected.processing_route || []).map((x,i)=><span key={x}>{i>0 && <ArrowRight size={14}/>}<em>{x}</em></span>)}</div></div></div>
        {!!detected.missing_information?.length && <div className="gapPanel"><CircleHelp size={18}/><div><b>Recommended supporting information</b><ul>{detected.missing_information.map((x,i)=><li key={i}>{x}</li>)}</ul></div></div>}
        {!!detected.blocking_gaps?.length && <div className="blockerPanel"><AlertTriangle size={18}/><div><b>Production blockers</b><ul>{detected.blocking_gaps.map((x,i)=><li key={i}>{x}</li>)}</ul></div></div>}
      </>}
    </Card>
    <Card title={`${models.length || 14} Supported Upload Models`}>
      <div className="modelGrid">{models.map(m => <ModelCard key={m.id} model={m} detected={m.id === detected?.model_id}/>)}</div>
      {!models.length && <div className="note">Upload a project to load the model catalogue and automatic classification.</div>}
    </Card>
  </div>;
}
