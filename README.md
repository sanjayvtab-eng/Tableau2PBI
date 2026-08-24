# TABLEAU2PBI Enterprise Migration Workbench V10.1

V10.1 fixes the frontend/backend version guard and keeps the compact dropdown-driven 360 Summary plus TDE Source Recovery views. Long Tableau projects are reviewed through focused dropdown sections instead of one lengthy page. It continues to treat `.tde` files as legacy validation/fallback artifacts and uses recovered original source details for production Power BI migration.

# TABLEAU2PBI Enterprise Migration Workbench

Professional web application for analyzing Tableau projects and generating a Power BI migration package.

## Core rule for TDE
When `.tde` is detected, the app treats it as a legacy output artifact / materialized snapshot / validation baseline. It does **not** design Power BI as `Tableau TDE -> Power BI`. The preferred architecture is:

`Original source systems -> reusable transformation layer -> Power BI semantic model -> DAX measures -> reports`

Use `.tde` only for validation or temporary static fallback when original sources and Tableau metadata are unavailable.

## Recommended upload ZIP contents
- `.twb` or `.twbx` Tableau workbook
- `.tds` or `.tdsx` Tableau data source
- `.tfl` or `.tflx` Tableau Prep flow when extract/prep logic exists
- Source files: `.csv`, `.xlsx`, `.xls`, `.txt`, `.json`, `.xml`, `.parquet`
- SQL scripts, database view definitions, or source documentation
- Extracts: `.tde`, `.hyper` only as validation/fallback references
- Optional TDE lineage file: `*.tde.meta.json`, `*_tde_logic.json`, or `extract_lineage.json`
- Images/background assets/custom shapes
- Optional validation baselines: row counts, Tableau totals, screenshots, extracts summary

## Run locally on Windows
Use a short path where possible, for example `C:\T2PBI`.

```powershell
cd "C:\T2PBI\t2pbi_workbench"
Set-ExecutionPolicy -Scope Process Bypass -Force
.\start_tableau2pbi.ps1
```

Backend health:

```text
http://127.0.0.1:8000/api/health
```

Frontend:

```text
http://127.0.0.1:5173
```

Expected backend version: `10.1.0`.

## UI improvements in V10
- Source area is split into **Source Overview** and **Source Mapping** to avoid one long screen.
- **TDE Source Recovery** is now a dedicated screen for TDE handling, source replacement, and source-column validation.
- TDE source details can be edited, saved, and used to regenerate preview/profile/M/DAX/validation output.
- Export includes `validation/tde_source_column_validation.json` and `.csv`.

## Included test package

```text
test_packages\complex_tableau_tde_retail_migration_test_package_v10.zip
```

It includes Tableau workbook/data source/prep flow metadata, source files, SQL, TDE and Hyper placeholders, TDE lineage metadata, dashboard/sheet visual encodings, parameters, LOD calculations, table calculations, RAWSQL and external model-extension examples.

## Export package contents
- Migration_Report.md
- docs/APPLICATION_INPUT_GUIDE.md
- inventory/file_inventory.json
- source_mapping/source_mapping.json
- source_mapping/tde_source_mapping.csv
- lineage/project_lineage.json
- lineage/tde_source_lineage.json
- migration_strategy/migration_decisions.json
- migration_strategy/tde_extract_strategy.json
- migration_strategy/tde_rebuild_plan.md
- migration_strategy/tde_recovered_logic.json
- validation/validation_report.json
- validation/reconciliation_plan.json
- validation/tde_reconciliation_plan.json
- validation/tde_baseline_metrics.json
- validation/tde_source_column_validation.json
- validation/tde_source_column_validation.csv
- manual_review/tde_manual_review_items.csv
- m_queries/*.pq
- dax/*.dax
- visuals/visual_build_plan.json
- PowerBI_PBIP_SafeMode skeleton

## Safe Openable Mode
Unsupported or risky Tableau logic is preserved in validation/manual-review artifacts instead of being written as invalid Power Query, DAX, or PBIR visuals.


## Render Deployment

This package includes `render.yaml` at the repository root and `README_RENDER_DEPLOYMENT.md` with step-by-step Render deployment instructions.
