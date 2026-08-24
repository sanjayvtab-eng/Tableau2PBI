# TABLEAU2PBI v11.6.2 - Windows Frontend Working-Directory Hotfix

This hotfix addresses the Windows npm ENOENT error where `npm install` attempted to read `t2pbi_workbench\package.json` instead of `t2pbi_workbench\frontend\package.json`.

## Root cause
The v11.6.1 launcher used `npm --prefix <frontend> install`. On the affected Windows/npm execution path, npm still resolved the package root from the parent workbench directory.

## Fix
- `run_frontend.ps1` now uses `Push-Location <workbench>\frontend` before *every* npm operation.
- `npm install` executes directly from the frontend folder.
- `npm run dev -- --strictPort` also executes directly from the frontend folder.
- The launcher validates `frontend/package.json`, `frontend/index.html`, and `frontend/vite.config.ts` before starting.
- Public npm registry remains pinned to `https://registry.npmjs.org/` for first-run install.
- Subsequent starts skip installation when `frontend/node_modules/.bin/vite.cmd` exists.

## Expected first-run behavior
1. Start `START_TABLEAU2PBI.cmd` from the workbench root.
2. Backend starts and becomes healthy.
3. Frontend window reports the explicit frontend path.
4. Dependencies install once under `frontend/node_modules`.
5. Vite starts on `http://127.0.0.1:5173`.
6. Browser opens only after the frontend returns HTTP 200.

Users should not run `npm run dev` from the project root.
