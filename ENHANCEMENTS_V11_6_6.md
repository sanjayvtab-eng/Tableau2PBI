# TABLEAU2PBI v11.6.6 — Schema Alignment & Final Table Safety

## Fixed Power BI missing-column load errors
- Excel mappings now navigate from the `Excel.Workbook` navigation result into the actual worksheet/table before promoting headers and applying types.
- Safe Openable Mode no longer emits fake database connections using `<server>` / `<database>` values.
- Unresolved database/manual sources now emit zero-row schema-preserving M tables so model source columns exist and Power BI can deserialize/open safely.
- Semantic M generation receives the exact final source-column schema used by `model.bim`.

## Improved final-table selection
- When the same conceptual table is represented by both an unresolved Tableau/database connection and a readable packaged business file, the readable source wins.
- JSON/XML package sidecars remain inventory/audit artifacts unless explicitly referenced by Tableau metadata.
- Existing duplicate-table and model-wide duplicate-measure protection remains active.

## Regression tests
- `backend/semantic_cleanup_regression_test.py`
- `backend/schema_alignment_regression_test.py`
- `backend/path_regression_test.py`
