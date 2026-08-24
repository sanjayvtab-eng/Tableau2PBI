# TABLEAU2PBI v11.6.1 - Startup Reliability Hotfix

## Fixed
- Vite is now launched with `frontend` as an explicit root, independent of the terminal working directory.
- Startup validates `frontend/index.html`, `package.json`, and `vite.config.ts` before launching.
- `npm install` uses `--prefix frontend` and only runs when the local Vite executable is absent.
- Startup uses a strict public npm registry setting.
- Main launcher waits for backend `/api/health` instead of assuming an 8-second startup.
- Main launcher waits for a real HTTP 200 from the frontend before opening the browser.
- Frontend uses strict port 5173, preventing silent port drift.
- Backend startup avoids unnecessary pip self-upgrade and runs Uvicorn without development reload.
- Clear errors are shown if the ZIP was incompletely extracted.

## Recommended startup
Double-click `START_TABLEAU2PBI.cmd` from the application root. Do not run `npm run dev` from the project root.
