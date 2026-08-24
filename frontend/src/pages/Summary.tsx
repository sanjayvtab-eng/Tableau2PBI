import { useMemo, useState } from 'react';
import { Card, Metric, Badge } from '../components/Cards';
import DataTable from '../components/DataTable';
import { MigrationProject } from '../types/project';

const DETAIL_OPTIONS = [
  'TDE strategy',
  'Dashboard inventory',
  'Worksheet and visual inventory',
  'Data source inventory',
  'Calculated logic inventory',
  'File inventory',
  'All summary metrics'
];

function pick(summary: Record<string, unknown>, ...keys: string[]) {
  for (const k of keys) if (summary[k] !== undefined) return summary[k];
  return 0;
}

function formatLabel(key: string) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function cleanJson(value: unknown) {
  if (Array.isArray(value)) return value.join(', ');
  if (value && typeof value === 'object') return JSON.stringify(value);
  return value;
}

export default function Summary({ project }: {project: MigrationProject}) {
  const [detail, setDetail] = useState(DETAIL_OPTIONS[0]);
  const tone = project.health_status === 'Ready' ? 'good' : project.health_status === 'Blocked' ? 'bad' : 'warn';
  const summary = project.summary || {};

  const tdeScenario = String(pick(summary, 'tde_strategy_scenario', 'TDE strategy scenario') || (project.tde_analysis?.[0] as any)?.scenario_classification || 'No TDE detected');
  const tdeRule = String(pick(summary, 'tde_source_of_truth_rule', 'TDE source-of-truth rule') || (project.tde_analysis?.length ? 'TDE is validation/fallback only' : 'No legacy TDE dependency'));

  const kpis = [
    { label: 'Workbook', value: pick(summary, 'workbook_name', 'Workbook name') || project.project_name },
    { label: 'Readiness', value: project.health_status },
    { label: 'Dashboards', value: pick(summary, 'dashboards', 'Dashboards') },
    { label: 'Worksheets', value: pick(summary, 'worksheets', 'Worksheets') },
    { label: 'Data sources', value: pick(summary, 'data_sources', 'Data sources') },
    { label: 'Source mappings', value: pick(summary, 'source_mappings', 'Source mappings') },
    { label: 'Calculated fields', value: pick(summary, 'calculated_fields', 'Calculated fields') },
    { label: 'TDE/extract files', value: pick(summary, 'extract_files', 'Extract files') },
  ];

  const compactRows = useMemo(() => [
    { area: 'Report structure', dashboards: pick(summary, 'dashboards', 'Dashboards'), worksheets: pick(summary, 'worksheets', 'Worksheets'), stories: pick(summary, 'stories', 'Stories'), visuals: project.visual_plan?.length || 0 },
    { area: 'Data model', data_sources: pick(summary, 'data_sources', 'Data sources'), source_mappings: project.source_mappings?.length || 0, relationships: pick(summary, 'relationships', 'Relationships'), joins: pick(summary, 'joins', 'Joins') },
    { area: 'Logic', calculated_fields: project.calculations?.length || 0, parameters: pick(summary, 'parameters', 'Parameters'), filters: pick(summary, 'filters', 'Filters'), unsupported: pick(summary, 'unsupported_objects', 'Unsupported objects') },
    { area: 'TDE strategy', scenario: tdeScenario, rule: tdeRule, tde_items: project.tde_analysis?.length || 0, export_mode: 'Safe Openable Mode' },
  ], [project, summary, tdeScenario, tdeRule]);

  const visualRows = project.visual_plan.map((v: any) => ({
    worksheet: v.worksheet,
    tableau_marks_type: v.tableau_marks_type,
    recommended_powerbi_visual: v.recommended_powerbi_visual,
    fields_used: cleanJson(v.fields_used || []),
    manual_review_notes: cleanJson(v.manual_review_notes || [])
  }));

  const worksheetRows = project.worksheets.map((w: any) => ({
    worksheet: w.name,
    marks_type: w.marks_type,
    rows_shelf: cleanJson(w.rows || []),
    columns_shelf: cleanJson(w.columns || []),
    filters: cleanJson(w.filters || []),
    encodings: cleanJson(w.encodings || {}),
    fields_used: cleanJson(w.fields_used || [])
  }));

  const calcRows = project.calculations.map(c => ({
    name: c.name,
    datasource: c.datasource,
    classification: c.classification,
    target: c.target_object_type,
    confidence: c.confidence_score,
    formula: c.formula,
    generated_expression: c.generated_expression,
    dependencies: cleanJson(c.dependencies),
    used_in: cleanJson(c.used_in),
    warnings: cleanJson(c.warnings),
    manual_review_notes: cleanJson(c.manual_review_notes)
  }));

  const datasourceRows = project.datasources.map((ds: any) => ({
    name: ds.name,
    source_kind: ds.source_kind,
    extract_or_live: ds.extract_or_live,
    connections: ds.connections?.length || 0,
    fields: ds.fields?.length || 0,
    relations: ds.relations?.length || 0,
    filters: ds.filters?.length || 0,
    aliases: ds.aliases?.length || 0
  }));

  const tdeRows = (project.tde_analysis || []).map((r: any) => ({
    tde_file: r.tde_file,
    tde_role: r.tde_role,
    is_source_of_truth: r.is_source_of_truth,
    scenario: r.scenario,
    scenario_classification: r.scenario_classification,
    decision: r.decision,
    preferred_architecture: r.preferred_architecture,
    temporary_fallback: r.temporary_fallback,
    validation_pattern: r.validation_pattern
  }));

  function detailBody() {
    switch (detail) {
      case 'TDE strategy':
        return <>
          <div className="summaryDecisionBox">
            <b>TDE rule:</b> The application ignores .tde as a production Power BI source when Tableau metadata or original source details are available. It uses the .tde as validation baseline or temporary fallback only. Use the dedicated <b>TDE Source Recovery</b> page to set original source details and validate source columns.
          </div>
          <DataTable rows={tdeRows as Record<string, unknown>[]} empty="No legacy .tde extracts detected"/>
        </>;
      case 'Dashboard inventory':
        return <DataTable rows={project.dashboards as Record<string, unknown>[]} empty="No dashboards detected"/>;
      case 'Worksheet and visual inventory':
        return <div className="stackedTables">
          <h3>Worksheet shelves and encodings</h3><DataTable rows={worksheetRows as Record<string, unknown>[]} empty="No worksheets detected"/>
          <h3>Power BI visual recommendations</h3><DataTable rows={visualRows as Record<string, unknown>[]} empty="No visual plan detected"/>
        </div>;
      case 'Data source inventory':
        return <DataTable rows={datasourceRows as Record<string, unknown>[]} empty="No data sources detected"/>;
      case 'Calculated logic inventory':
        return <DataTable rows={calcRows as Record<string, unknown>[]} empty="No calculations detected"/>;
      case 'File inventory':
        return <DataTable rows={project.inventory.map(i => ({ folder_path: i.folder_path, file_name: i.file_name, extension: i.extension, role: i.role, status: i.parsed_status, size_bytes: i.size_bytes, warnings: cleanJson(i.warnings), errors: cleanJson(i.errors) })) as Record<string, unknown>[]} empty="No files inventoried"/>;
      default:
        return <DataTable rows={Object.entries(summary).map(([metric, value]) => ({ metric: formatLabel(metric), value }))} empty="No summary metrics"/>;
    }
  }

  return <div className="page summaryPage">
    <Card title="Tableau 360 Summary" right={<Badge tone={tone}>{project.health_status}</Badge>}>
      <div className="summaryHeroCompact">
        <div>
          <p className="eyebrow">Executive migration snapshot</p>
          <h1>{String(pick(summary, 'workbook_name', 'Workbook name') || project.project_name)}</h1>
          <p className="muted">The 360 view is intentionally compact. Use the dropdown below to inspect dashboards, worksheets, data sources, calculations, visual plans, TDE strategy, and full file inventory without scrolling through one long page.</p>
        </div>
        <div className="summaryStatusPanel">
          <span className={`statusDot ${tone}`}></span>
          <b>{project.health_status}</b>
          <small>{tdeScenario}</small>
          <small>{tdeRule}</small>
        </div>
      </div>
      <div className="summaryKpiGrid">{kpis.map(k => <Metric key={k.label} label={k.label} value={k.value}/>)}</div>
    </Card>

    <Card title="Compact Migration Health by Area">
      <DataTable rows={compactRows as Record<string, unknown>[]}/>
    </Card>

    <Card title="Review Details" right={<select className="detailSelect" value={detail} onChange={e => setDetail(e.target.value)}>{DETAIL_OPTIONS.map(x => <option key={x}>{x}</option>)}</select>}>
      <div className="summaryDetailPanel">{detailBody()}</div>
    </Card>
  </div>;
}
