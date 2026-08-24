# TABLEAU2PBI v11.6.5 — Semantic Cleanup Hardening

## Fixed

- Unreferenced `.json` and `.xml` files inside Tableau ZIP/TWBX/TDSX/TFLX packages are now inventory/audit artifacts only and are not promoted into Source Mapping or the final Power BI semantic model.
- JSON/XML remain fully supported when Tableau explicitly references them as a source or when they are uploaded directly as the intended source.
- Metadata/configuration JSON/XML files are explicitly classified as `Metadata/support file - not model table` where detectable.
- Duplicate measure names are deduplicated across the entire semantic model, not only within one table.
- When duplicate measure definitions conflict, Safe Openable Mode retains the higher-confidence canonical measure and records a review recommendation.
- PBIP export has a second global duplicate-measure guard.
- PBIP integrity validation now checks duplicate measures and measure/column name collisions.

## Final-model-first rule

Only business tables that are genuinely referenced/recovered from Tableau source metadata are promoted into the Power BI model. Package support files remain visible in File Inventory for traceability without creating unwanted model tables.
