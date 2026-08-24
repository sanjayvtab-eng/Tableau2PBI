# TABLEAU2PBI v11.6.4 — Semantic Model Duplicate Object Hardening

Fixes the Power BI Desktop error: `Cannot de-serialize Database. Error: Item '<name>' already exists in the collection.`

## Changes
- Calculations from federated/helper Tableau datasources are no longer incorrectly attached to the first final Power BI table.
- Measure names are deduplicated case-insensitively per semantic table.
- Calculated-column names are deduplicated case-insensitively per semantic table.
- Column/measure namespace collisions are suppressed in Safe Openable Mode.
- Known Tableau-only / invalid DAX patterns are excluded from `model.bim` and remain available for migration review instead of breaking PBIP openability.
- Existing short-path PBIP hardening from v11.6.3 is retained.
