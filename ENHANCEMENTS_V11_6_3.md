# TABLEAU2PBI v11.6.3 — PBIP Windows Short-Path Hard Fix

## Fixed
- PBIP export no longer repeats the Tableau/workbook name in nested package folders.
- Download ZIP now uses a short stable ID: `T2PBI_Pxxxxxxxx.zip`.
- PBIP content is rooted directly under `PBI/` with short artifact names.
- Semantic model/report folders use the same short stable ID instead of long workbook names.
- ZIP creation no longer adds an extra package-name directory level.
- `OPEN_THIS_PBIP.cmd` opens the short-path PBIP directly.
- Export pre-validation includes the deepest Power BI-created path (`.SemanticModel/.pbi/editorSettings.json`) in the path budget.
- Full Tableau/workbook name is preserved in migration metadata/reports rather than physical Windows paths.
- `_safe_file_stem` now guarantees the returned value stays within the requested maximum length including its hash suffix.

## Regression tested
A deliberately long project name was exported through the complex Tableau retail test package. The resulting PBIP path was `PBI/Pxxxxxxxx.pbip`, the deepest generated ZIP entry was 54 characters, and final PBIP structural validation passed.
