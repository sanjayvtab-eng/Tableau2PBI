# TABLEAU2PBI V11 Enhancements

## Added
- Demo login page (`balamuraleee@gmail.com` / `12345`). Replace with enterprise SSO before production.
- File Mode Processing Tree for ZIP, TWBX, TDSX, TFLX, TWB, TDS, TFL, Hyper, TDE, tabular files, structured files and SQL.
- TDE nodes explicitly list the supporting information required to recover original source logic.
- Semantic model design engine excludes legacy TDE, temporary, staging, helper, intermediate, anonymous, join-payload and union-payload tables.
- Duplicate technical columns introduced by joins are cleaned before relationship inference while preserving the first business-key occurrence.
- AI-style recommendations are included in project JSON for semantic model, joins and calculation placement.
- Persistent Go-to-Top control and sign-out action.
- Backend version 11.0.0.

## Validation performed
The backend pipeline was executed against `complex_tableau_tde_retail_migration_test_package_v10.zip`:
- 43 inventory items
- 3 TDE nodes detected
- TDE analysis generated
- 12 semantic tables generated after exclusion rules
- Result: Ready with warnings

## Important
The frontend dependencies are not bundled in `node_modules`. Run `npm install` in `frontend` before `npm run build` or starting Vite.
