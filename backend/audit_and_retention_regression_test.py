from __future__ import annotations
import os
import tempfile
import io
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.core.audit_logger import log_event, get_recent_audit_logs
from app.services.storage import new_project_dir, delete_project
from app.models.schemas import MigrationProject
from app.core.config import settings

client = TestClient(app)

def test_audit_logging():
    log_event("TEST_EVENT", user_id="tester@vtab.com", project_id="p123", status="SUCCESS", details={"metric": 42})
    logs = get_recent_audit_logs(limit=10)
    assert len(logs) > 0
    latest = logs[-1]
    assert latest["event_type"] == "TEST_EVENT"
    assert latest["user_id"] == "tester@vtab.com"
    assert latest["project_id"] == "p123"
    print("Audit logging test: PASS")

def test_project_deletion_api():
    pid, ppath = new_project_dir("test_delete")
    assert ppath.exists()
    
    # Test DELETE endpoint
    res = client.delete(f"/api/projects/{pid}")
    assert res.status_code == 200
    assert res.json()["deleted"] is True
    assert not ppath.exists()
    
    # Second delete returns 404
    res2 = client.delete(f"/api/projects/{pid}")
    assert res2.status_code == 404
    print("Project deletion API test: PASS")

def test_audit_logs_endpoint():
    res = client.get("/api/audit-logs?limit=5")
    assert res.status_code == 200
    data = res.json()
    assert "audit_logs" in data
    assert isinstance(data["audit_logs"], list)
    print("Audit logs endpoint test: PASS")

if __name__ == "__main__":
    test_audit_logging()
    test_project_deletion_api()
    test_audit_logs_endpoint()
    print("ALL AUDIT AND RETENTION TESTS PASSED")
