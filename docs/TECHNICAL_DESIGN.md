# Technical Design

## Compiler-style pipeline

1. Upload and extraction engine
2. Package extractor for ZIP/TWBX/TDSX/TFLX using short Windows-safe folders
3. File inventory and role detection
4. Tableau XML parse engine
5. Hyper/TDE metadata review hooks
6. Workbook/datasource metadata model creation
7. Logical data model, physical join/union, custom SQL, and blend/federated-source classification
8. Calculation extraction and dependency analysis
9. Parameter/filter/action/set/group/bin inventory where metadata is available
10. Source mapping and credential planner
11. Data preview and profiling
12. Data type inference and override propagation
13. Migration strategy decision engine
14. M query generation
15. DAX generation
16. Semantic model assembly
17. Relationship inference and designer updates
18. Visual conversion planning
19. Validation, reconciliation planning, and safe export

Every pipeline stage updates structured JSON stored in the runtime workspace project model. Downstream stages use this JSON model and do not reparse raw Tableau XML independently.

## V7 migration strategy engine

The strategy engine decides where Tableau logic belongs in Power BI:

- Tableau relationship: semantic model relationship; not Power Query Merge by default.
- Physical join: Power Query Merge / source SQL only when physical output is required.
- Union: Power Query Append.
- Tableau blend/federated behavior: Power BI semantic model, bridge table, composite model, or manual review.
- Row-level deterministic calculation: Power Query column or DAX calculated column.
- Aggregation: DAX measure.
- LOD: DAX CALCULATE pattern with validation.
- Table calculation: DAX/manual review because partition/addressing depends on visual context.
- RAWSQL/external analytics/model extensions: manual review / source SQL review.
- Tableau-generated fields and visual-only formatting: omitted unless business-used.

## Safe-mode export

The export writer creates review-ready Power BI artifacts and avoids experimental visual/report injection by default. This protects users from invalid PBIP structures when a Tableau feature cannot be safely represented in Power BI.

Export includes:

- PowerBI_PBIP_SafeMode skeleton
- M query files
- DAX/manual-review files
- file inventory JSON
- source mapping JSON
- semantic model JSON
- visual build plan JSON
- migration strategy decisions JSON
- reconciliation plan JSON
- validation report JSON
- migration report Markdown

## Accuracy model

The application aims for deterministic parser/converter accuracy where Tableau metadata is explicit. Business accuracy must be validated with the exported reconciliation plan because Tableau can produce context-specific worksheet queries, especially around relationships, order of operations, Top N/context filters, table calculations, FIXED/INCLUDE/EXCLUDE LODs, blending, and visual interactions.


## V7 TDE extract strategy engine

V7 treats `.tde` as a legacy materialized snapshot/output artifact. The target Power BI design is never `Tableau TDE -> Power BI` for production. The pipeline classifies TDE cases A-E, recovers source logic from TWB/TDS/TWBX/TDSX metadata where possible, maps original sources to Power BI connectors, and exports `migration_strategy/tde_extract_strategy.json` plus reconciliation checkpoints for TDE baseline validation.
