# v11.4 Upload Model & Processing Route Engine

This release enhances v11.3 so customer uploads are not only inventoried but classified into a migration model and routed to the correct downstream stage.

## Added
- Two-stage upload model classification: extension-based before parsing and metadata-aware refinement after TWB/TDS/TFL parsing.
- Distinguishes workbook-only/file-source/database-backed/extract/prep/partial models.
- Explicit model processing route and next application stage.
- Production rule for every supported upload model.
- Per-file migration purpose and next-stage routing in File Processing Tree.
- TDE routes to TDE Source Recovery and is never silently treated as production source.
- Hyper is treated as extract evidence/validation by default when original source lineage is available.
- Missing-information and production-blocker gates.
- Fixed duplicate inventory entries for plain non-package uploads.

## Model routing examples
- TWB + CSV -> Workbook + Source Files -> Preview & Types
- TWB/TWBX with parsed database metadata -> Workbook + Database Details -> Source Mapping
- TDE/Hyper + TWB/TDS metadata -> Extract + Tableau Metadata -> TDE Source Recovery
- TDE/Hyper only -> Extract Only -> TDE Source Recovery / manual lineage recovery
- TFL/TFLX -> Tableau Prep Project -> Source Mapping / preparation reconstruction
- Partial metadata -> Partial or Missing-Source Project -> Source Mapping with blockers

## Safety rule
The detected model controls the recommended path, but unsupported or incomplete lineage remains visible and can block unsafe production export.
