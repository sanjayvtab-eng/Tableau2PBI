from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router
from app.core.config import settings

app = FastAPI(title=settings.app_name, version=settings.version)

app.add_middleware(
    CORSMiddleware,
    # Allow local Vite dev ports such as 5173/5174 and avoid upload failures when Vite
    # automatically selects the next available port.
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

frontend_dist_env = os.environ.get("FRONTEND_DIST", "/app/frontend/dist")
frontend_dist_path = Path(frontend_dist_env)

if frontend_dist_path.exists() and (frontend_dist_path / "index.html").exists():
    assets_dir = frontend_dist_path / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        requested_file = frontend_dist_path / full_path
        if full_path and requested_file.is_file():
            return FileResponse(str(requested_file))
        return FileResponse(str(frontend_dist_path / "index.html"))
else:
    @app.get("/")
    def root():
        return {"application": settings.app_name, "version": settings.version, "docs": "/docs", "health": "/api/health"}

