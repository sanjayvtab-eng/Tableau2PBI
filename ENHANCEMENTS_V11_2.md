# v11.2 Upload Model Guidance

Implemented:

- 14 customer upload models with mandatory and optional artifacts.
- Automatic upload-model classification after inventory.
- Missing-information detection for workbook-only, partial-project and extract-only cases.
- New **Upload Models** page with extraction guidance and readiness notes.
- Upload page enhanced to explain supported customer scenarios and security restrictions.
- New API endpoint: `GET /api/upload-models`.
- Project response fields: `upload_model` and `upload_model_catalogue`.
- Dedicated `UPLOAD_MODELS_GUIDE.md` for user education.

Validation performed:

- Python backend compilation completed successfully.
- Demo pipeline executed successfully and classified `.twb + .csv` as **Workbook + Source Files**.
- Catalogue returned 14 upload models.

Frontend source changes are included. Run `npm install` before `npm run dev` or `npm run build` on a machine with normal npm registry access.
