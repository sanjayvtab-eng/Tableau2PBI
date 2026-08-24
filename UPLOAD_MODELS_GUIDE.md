# TABLEAU2PBI Upload Models Guide — v11.2

The workbench supports 14 customer delivery models. The application automatically classifies uploaded assets and displays mandatory files, optional evidence, missing information and extraction notes.

## Core rules

- Upload the original Tableau files whenever possible.
- Preserve filenames and relative folder structures.
- A TWB/TDS/TFL is metadata; it may not contain source data.
- A TWBX/TDSX/TFLX is a package and may contain local files or extracts.
- Hyper/TDE extracts are outputs, not the preferred long-term source of truth.
- Never upload passwords, PAT tokens, private keys or connection secrets.
- Where files are unavailable, provide source system, SQL, refresh, key, datatype, row-count and business-total documentation.

## How to obtain common artifacts

- **TWBX:** Tableau Desktop > File > Save As > Tableau Packaged Workbook.
- **TWB:** Tableau Desktop > File > Save As > Tableau Workbook.
- **TDS/TDSX:** Save or add the Tableau data source to Saved Data Sources; choose packaged format when local assets must be included.
- **TFL/TFLX:** Tableau Prep Builder > File > Save As; use packaged flow where supported.
- **Server/Cloud workbook:** Download > Tableau Workbook, subject to permissions.
- **Packaged contents:** Work on a copy. A TWBX/TDSX/TFLX is ZIP-based; rename the copy to `.zip` to inspect embedded metadata/data. Do not overwrite the original.
- **Hyper/TDE:** Look inside packaged workbooks/data sources, Tableau repository directories, or request the extract from the workbook owner/server administrator.

The application treats missing assets as explicit migration gaps; it does not silently invent lineage or substitute unrelated data.
