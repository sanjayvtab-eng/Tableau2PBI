# TABLEAU2PBI v11.5 – PBIP Integrity & Source Path Hardening

This release hardens source-path mapping, M parameter generation, semantic model generation, relationship safety, and PBIP structural validation.

## Covered findings
- model.bim is written as UTF-8 without BOM and revalidated before export.
- `defaultPowerBIDataSourceVersion` is emitted only as `powerBI_V3`.
- model.bim JSON is generated from a constrained schema; invalid extra relationship/calculation metadata is not serialized into model objects.
- Local-file M uses one generated `<table>_<id>_SourcePath` M parameter per mapped local source. No generic `SourceFolder` parameter is generated.
- CSV/Text/Excel/JSON/XML/Parquet paths are normalized and resolved; raw relative paths are never written directly into `File.Contents()`.
- Explicit absolute Windows/UNC and POSIX paths are preserved. Uploaded/packaged files are resolved to a real absolute workspace file only when the match is deterministic; identical duplicate package copies use a canonical copy; conflicting duplicates remain unresolved and block safe export.
- Semantic tables exclude legacy TDE, Hyper/extract artifacts used as validation sources, Tableau internal/generated objects, and temporary/intermediate objects.
- Duplicate semantic table names are detected; exact duplicate mappings are removed and conflicting names are deterministically renamed for review.
- Relationship inference uses key/profile/name/type evidence; uncertain one-to-one and many-to-many candidates remain manual review/inactive.
- Only one inferred active relationship is allowed per table pair and inferred cycles are deactivated to prevent ambiguous filter paths.
- Relationship cardinality/cross-filter values are converted to valid model.bim values before export.
- Final PBIP structural validation parses `.pbip`, `definition.pbir`, and `model.bim`, checks BOM, JSON, PowerBIDataSourceVersion, tables, M let/in structure, path parameter references, relationship references/cardinality, duplicate relationship pairs, and active cycles.
- `validation/pbip_integrity_validation.json` is included in every successful export.

## Power BI Desktop validation boundary
The exporter performs structural validation against the exact PBIP files before they are zipped. Power BI Desktop itself cannot be launched in the Linux build/test runtime. Therefore the application does not falsely mark “opened successfully in Power BI Desktop” as tested. Final Desktop open/refresh/business reconciliation remains a Windows acceptance step.
