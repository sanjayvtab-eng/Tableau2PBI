# TABLEAU2PBI v11.6.0 - Final Model First UX

- Collapses duplicate source representations into one canonical final semantic table.
- Excludes TDE/Hyper, metadata sidecars, lineage/validation files, Tableau-generated and temporary/internal tables from the business semantic model.
- Source Mapping defaults to business/original sources; extract artifacts are available only as an explicit validation/recovery view.
- Relationship inference emits only one safe final relationship per table pair and prevents ambiguous/cyclic inferred paths.
- Relationship UI shows only final active model relationships by default.
- Final Tables uses a compact table selector instead of vertically stacking technical tables.
- Simplified final-model-first UI with clear KPIs, status badges, compact relationship flows, and technical lineage collapsed by default.
- Frontend startup installs dependencies only on first run and uses the public npm registry.
