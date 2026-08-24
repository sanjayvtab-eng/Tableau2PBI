# v11.3 Production-Grade PBIP Export Engine

## Added
- Export pre-validation for workspace, write permissions, safe path length, project metadata, semantic metadata, and validation metadata.
- Automatic parent-directory creation before every file write.
- Safe, shortened file and folder names suitable for Windows paths.
- Transactional export generation in a staging directory.
- Atomic commit with rollback to the previously successful package if commit fails.
- Temporary ZIP creation followed by atomic replacement.
- ExportLog.json and ExportLog.html containing pre-validation, generated files, status, warnings, errors, and manual actions.
- Safe-mode warnings for legacy TDE artifacts, missing semantic tables, and unresolved validation issues.

## Export output
The export folder and ZIP now use a shorter `<project>_PBIP_Export` name. The prior successful export is preserved until the new export completes successfully.
