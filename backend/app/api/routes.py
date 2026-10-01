from __future__ import annotations
import os
import logging
import jwt
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from fastapi.responses import FileResponse
from app.exporters.package_writer import write_export
from app.models.schemas import MigrationProject, RelationshipCandidate, SourceMapping
from app.services.pipeline import run_pipeline, _build_semantic_tables
from app.core.config import settings
from app.services.storage import load_project, new_project_dir, persist_project, save_upload, delete_project
from app.services.data_profiler import preview_mapping
from app.services.relationship_builder import infer_relationships
from app.services.visual_planner import build_visual_plan
from app.validators.rules import validate_project, health_from_issues
from app.services.migration_strategy import build_migration_decisions, build_reconciliation_plan, add_strategy_validation_issues, add_tde_validation_issues, build_tde_analysis
from app.services.upload_model_engine import catalogue
from app.services.path_parameter_engine import configure_project_paths
from app.core.audit_logger import log_event, get_recent_audit_logs

logger = logging.getLogger("tableau2pbi.api")

router = APIRouter(prefix="/api", tags=["tableau2pbi"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(payload: LoginRequest):
    if not settings.auth_username or not settings.auth_password:
        log_event("LOGIN", user_id=payload.username.strip(), status="FAILED", details={"reason": "Auth not configured"})
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured. Set T2PBI_AUTH_USERNAME and T2PBI_AUTH_PASSWORD in the deployment environment.",
        )
    if (
        payload.username.strip().casefold() == settings.auth_username.strip().casefold()
        and payload.password == settings.auth_password
    ):
        log_event("LOGIN", user_id=payload.username.strip(), status="SUCCESS")
        return {
            "authenticated": True,
            "display_name": payload.username.strip(),
            "role": "Migration Administrator",
            "demo_auth": False,
        }
    log_event("LOGIN", user_id=payload.username.strip(), status="FAILED", details={"reason": "Invalid credentials"})
    raise HTTPException(status_code=401, detail="Invalid username or password.")


class VTABSSORequest(BaseModel):
    token: str

@router.post("/auth/vtab-sso")
def vtab_sso(payload: VTABSSORequest):
    sso_secret = os.environ.get("VTAB_SSO_SECRET")
    if not sso_secret:
        raise HTTPException(status_code=500, detail="Server missing VTAB_SSO_SECRET")
    
    try:
        decoded = jwt.decode(
            payload.token,
            sso_secret,
            algorithms=["HS256"],
            audience="tableau2pbi",
            issuer="vtab360"
        )
        
        if decoded.get("purpose") != "vtab_sso":
            log_event("SSO_LOGIN", status="FAILED", details={"reason": "Invalid token purpose"})
            raise HTTPException(status_code=400, detail="Invalid token purpose")
            
        user_email = decoded.get("email")
        log_event("SSO_LOGIN", user_id=user_email, status="SUCCESS")
        return {
            "authenticated": True,
            "display_name": user_email,
            "role": "VTAB SSO User",
            "demo_auth": False,
        }
    except jwt.ExpiredSignatureError:
        log_event("SSO_LOGIN", status="FAILED", details={"reason": "Token expired"})
        raise HTTPException(status_code=401, detail="SSO token has expired")
    except jwt.InvalidTokenError:
        log_event("SSO_LOGIN", status="FAILED", details={"reason": "Invalid token"})
        raise HTTPException(status_code=401, detail="Invalid SSO token")


@router.get("/upload-models")
def upload_models():
    return {"models": catalogue()}


@router.get("/health")
def health():
    return {
        "status": "ok",
        "application": "TABLEAU2PBI Enterprise Migration Workbench",
        "version": settings.version,
        "workspace": str(settings.storage_root),
        "auth_configured": bool(settings.auth_username and settings.auth_password),
    }


@router.post("/projects/upload", response_model=MigrationProject)
def upload_project(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one Tableau file or ZIP package.")
    project_name = Path(files[0].filename).stem
    project_id, project_path = new_project_dir(project_name)
    try:
        saved = [save_upload(project_path, f) for f in files]
    except ValueError as val_err:
        log_event("UPLOAD_PROJECT", project_id=project_id, status="FAILED", details={"error": str(val_err)})
        raise HTTPException(status_code=413, detail=str(val_err))
    
    project = MigrationProject(project_id=project_id, project_name=project_name, workspace_path=str(project_path))
    try:
        project = run_pipeline(project, saved)
    except Exception as exc:
        logger.error(f"Upload pipeline failed for project {project_id}: {exc}", exc_info=True)
        clean_err = str(exc).splitlines()[0] if str(exc) else "Internal processing error"
        if len(clean_err) > 200 or "Traceback" in clean_err:
            clean_err = "Internal pipeline processing error."
        log_event("UPLOAD_PROJECT", project_id=project_id, status="FAILED", details={"error": clean_err})
        raise HTTPException(status_code=500, detail=f"Upload pipeline failed: {clean_err}")
    
    persist_project(project)
    log_event("UPLOAD_PROJECT", project_id=project_id, status="SUCCESS", details={"files": [f.filename for f in files]})
    return project


@router.post("/projects/demo", response_model=MigrationProject)
def load_demo_project():
    base = Path(__file__).resolve().parents[3] / "sample_project"
    demo_files = [p for p in base.iterdir() if p.is_file()]
    project_id, project_path = new_project_dir("Demo_Superstore_Tableau")
    saved = []
    for source in demo_files:
        target = project_path / "uploads" / source.name
        target.write_bytes(source.read_bytes())
        saved.append(target)
    project = MigrationProject(project_id=project_id, project_name="Demo_Superstore_Tableau", workspace_path=str(project_path))
    project = run_pipeline(project, saved)
    persist_project(project)
    log_event("LOAD_DEMO_PROJECT", project_id=project_id, status="SUCCESS")
    return project


@router.get("/projects/{project_id}", response_model=MigrationProject)
def get_project(project_id: str):
    try:
        return load_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/projects/{project_id}/source-mappings", response_model=MigrationProject)
def update_source_mappings(project_id: str, mappings: list[SourceMapping]):
    project = load_project(project_id)
    project.source_mappings = mappings
    configure_project_paths(project)
    workspace = Path(project.workspace_path)
    project.previews = [preview_mapping(m, workspace) for m in project.source_mappings]
    project.semantic_tables = _build_semantic_tables(project)
    project.relationships = infer_relationships(project)
    project.visual_plan = build_visual_plan(project.worksheets)
    project.tde_analysis = build_tde_analysis(project)
    project.migration_decisions = build_migration_decisions(project)
    project.reconciliation_plan = build_reconciliation_plan(project)
    project.validation_issues = []
    add_strategy_validation_issues(project, project.migration_decisions)
    add_tde_validation_issues(project, project.tde_analysis)
    project.validation_issues = project.validation_issues + validate_project(project)
    project.health_status = health_from_issues(project.validation_issues)
    persist_project(project)
    log_event("UPDATE_SOURCE_MAPPINGS", project_id=project_id, status="SUCCESS", details={"mappings_count": len(mappings)})
    return project


@router.put("/projects/{project_id}/relationships", response_model=MigrationProject)
def update_relationships(project_id: str, relationships: list[RelationshipCandidate]):
    project = load_project(project_id)
    project.relationships = relationships
    project.tde_analysis = build_tde_analysis(project)
    project.migration_decisions = build_migration_decisions(project)
    project.reconciliation_plan = build_reconciliation_plan(project)
    project.validation_issues = []
    add_strategy_validation_issues(project, project.migration_decisions)
    add_tde_validation_issues(project, project.tde_analysis)
    project.validation_issues = project.validation_issues + validate_project(project)
    project.health_status = health_from_issues(project.validation_issues)
    persist_project(project)
    log_event("UPDATE_RELATIONSHIPS", project_id=project_id, status="SUCCESS", details={"relationships_count": len(relationships)})
    return project


@router.post("/projects/{project_id}/validate", response_model=MigrationProject)
def validate(project_id: str):
    project = load_project(project_id)
    project.tde_analysis = build_tde_analysis(project)
    project.migration_decisions = build_migration_decisions(project)
    project.reconciliation_plan = build_reconciliation_plan(project)
    project.validation_issues = []
    add_strategy_validation_issues(project, project.migration_decisions)
    add_tde_validation_issues(project, project.tde_analysis)
    project.validation_issues = project.validation_issues + validate_project(project)
    project.health_status = health_from_issues(project.validation_issues)
    persist_project(project)
    log_event("VALIDATE_PROJECT", project_id=project_id, status="SUCCESS", details={"health": project.health_status})
    return project


@router.post("/projects/{project_id}/export")
def export_project(project_id: str, request: Request):
    project = load_project(project_id)
    project.tde_analysis = build_tde_analysis(project)
    project.migration_decisions = build_migration_decisions(project)
    project.reconciliation_plan = build_reconciliation_plan(project)
    project.validation_issues = []
    add_strategy_validation_issues(project, project.migration_decisions)
    add_tde_validation_issues(project, project.tde_analysis)
    project.validation_issues = project.validation_issues + validate_project(project)
    project.health_status = health_from_issues(project.validation_issues)
    try:
        zip_path = write_export(project)
    except Exception as exc:
        logger.error(f"Export generation failed for project {project_id}: {exc}", exc_info=True)
        clean_err = str(exc).splitlines()[0] if str(exc) else "Internal export generation error"
        log_event("EXPORT_PROJECT", project_id=project_id, status="FAILED", details={"error": clean_err})
        raise HTTPException(status_code=500, detail=f"Export generation failed: {clean_err}")
    
    project.export_path = str(zip_path)
    persist_project(project)
    log_event("EXPORT_PROJECT", project_id=project_id, status="SUCCESS", details={"export_path": str(zip_path)})
    
    relative = f"/api/projects/{project_id}/export/download"
    absolute = str(request.base_url).rstrip("/") + relative
    return {
        "download_url": relative,
        "absolute_download_url": absolute,
        "export_path": str(zip_path),
        "health_status": project.health_status,
    }


@router.get("/projects/{project_id}/export/download")
def download_export(project_id: str):
    project = load_project(project_id)
    if not project.export_path or not Path(project.export_path).exists():
        zip_path = write_export(project)
        project.export_path = str(zip_path)
        persist_project(project)
    path = Path(project.export_path)
    return FileResponse(path, filename=path.name, media_type="application/zip")


@router.delete("/projects/{project_id}")
def delete_project_endpoint(project_id: str):
    try:
        deleted = delete_project(project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        log_event("DELETE_PROJECT", project_id=project_id, status="SUCCESS")
        return {
            "deleted": True,
            "project_id": project_id,
            "message": "Project and workspace storage successfully deleted."
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to delete project {project_id}: {exc}", exc_info=True)
        log_event("DELETE_PROJECT", project_id=project_id, status="FAILED", details={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to delete project.")


@router.get("/audit-logs")
def list_audit_logs(limit: int = 100):
    return {"audit_logs": get_recent_audit_logs(limit=limit)}

