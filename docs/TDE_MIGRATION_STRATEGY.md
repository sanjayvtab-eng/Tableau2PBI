# TDE Migration Strategy

`.tde` files are treated as legacy Tableau extract artifacts and validation baselines. They are ignored as production Power BI sources when original sources, Tableau metadata, SQL, or Prep flow logic is available.

## Strategy
1. Detect `.tde` in the inventory and mark it as Legacy TDE Extract.
2. Inspect TWB/TWBX/TDS/TDSX/TFL/TFLX and companion `*.tde.meta.json` files.
3. Recover upstream sources, custom SQL, joins, relationships, unions, extract filters, calculations, aliases, groups, type changes, pivot/unpivot, and incremental-refresh hints.
4. Build Power BI from original sources using Power Query, Dataflows, Fabric, or SQL staging.
5. Build a clean star schema and DAX measures.
6. Use TDE only to validate row counts, totals, distinct keys, filtered totals, Top N, percent-of-total, LOD, and table-calculation output.
7. Use direct TDE export only when no original source or metadata is available.
