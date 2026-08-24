import { ArrowRight, CheckCircle2, GitBranch, ShieldAlert, FileArchive, Eye, DatabaseZap, AlertTriangle } from 'lucide-react';
import { Card } from '../components/Cards';

export default function Landing({ onStart }: {onStart: () => void}) {
  return <div className="page">
    <div className="hero upgradedHero">
      <div>
        <p className="eyebrow">Compiler-style Tableau migration platform</p>
        <h1>TABLEAU2PBI Enterprise Migration Workbench</h1>
        <p>Upload Tableau workbooks, packaged workbooks, data sources, Prep flows, extracts and project ZIPs. The workbench inventories the package, recovers Tableau metadata, identifies original data-source logic, converts safe calculations to Power Query M / DAX, and exports a Power BI migration package with review and validation artifacts.</p>
        <div className="actions"><button className="primary" onClick={onStart}>Open Upload Workspace <ArrowRight size={16}/></button><span className="pill">Safe Openable Mode default</span><span className="pill">TDE ignored as production source</span></div>
      </div>
      <div className="architecture architectureWide">
        {['Upload package', 'Inventory nested files', 'Parse TWB/TDS/TFL XML', 'Recover TDE source logic', 'Source mapping & profiling', 'Model relationships', 'M/DAX conversion', 'Visual build plan', 'Validation & export'].map((s, i) => <div key={s}><span>{i+1}</span>{s}</div>)}
      </div>
    </div>

    <div className="grid2">
      <Card title="What should be inside the ZIP" right={<FileArchive size={18}/> }>
        <ul className="checkList compact"><li><CheckCircle2/> .twb/.twbx workbook and .tds/.tdsx data source files</li><li><CheckCircle2/> .tfl/.tflx Tableau Prep flow if it built the extract</li><li><CheckCircle2/> Source files used by Tableau: CSV, Excel, TXT, JSON, XML, Parquet</li><li><CheckCircle2/> SQL scripts, view definitions, or data-source documentation</li><li><CheckCircle2/> .tde/.hyper extracts only as validation or fallback references</li><li><CheckCircle2/> Optional *.tde.meta.json or extract_lineage.json with upstream-source details</li></ul>
      </Card>
      <Card title="TDE handling rule" right={<ShieldAlert size={18}/> }>
        <div className="tdeRuleBox"><b>Do not build Power BI as Tableau TDE → Power BI.</b><br/>When a .tde is detected, the app treats it as a legacy materialized snapshot. It recovers original sources from Tableau metadata and companion lineage files, rebuilds the model from those sources, and uses the TDE only for validation or temporary static export fallback.</div>
      </Card>
    </div>

    <div className="grid3">
      <Card title="What the app can do"><ul className="checkList"><li><DatabaseZap/> Inventory workbooks, sheets, dashboards, stories, sources, extracts, assets and nested packages</li><li><DatabaseZap/> Parse joins, relationships, unions, filters, parameters, groups, aliases, bins and calculated fields</li><li><DatabaseZap/> Show visual encodings and recommend equivalent Power BI visuals per worksheet</li><li><DatabaseZap/> Generate source mappings, previews, M queries, DAX review files, model metadata, validations and reports</li></ul></Card>
      <Card title="What requires validation"><ul className="checkList"><li><AlertTriangle/> Complex table calculations, external scripts, model extensions and ambiguous LOD behavior</li><li><AlertTriangle/> Credentials, gateway, server security, RLS intent and business metric sign-off</li><li><AlertTriangle/> Pixel-perfect Tableau dashboard layout and custom visuals/extensions</li><li><AlertTriangle/> Recovering upstream logic from a standalone TDE without Tableau metadata</li></ul></Card>
      <Card title="Enterprise stack"><ul className="checkList"><li><GitBranch/> FastAPI Python backend</li><li><GitBranch/> React + TypeScript frontend</li><li><GitBranch/> pandas/pyarrow profiling</li><li><GitBranch/> modular Tableau parser, TDE strategy engine, M/DAX translators and validation rules</li></ul></Card>
    </div>

    <Card title="How the application works">
      <div className="processFlow">
        {['Upload', 'Extract', 'Inventory', 'Parse', 'Recover TDE logic', 'Classify transformations', 'Generate M/DAX', 'Validate', 'Export'].map((x, i) => <div key={x}><b>{i+1}</b><span>{x}</span></div>)}
      </div>
    </Card>
  </div>;
}
