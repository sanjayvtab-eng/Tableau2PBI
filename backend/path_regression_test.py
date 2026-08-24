from pathlib import Path
import zipfile
from app.models.schemas import MigrationProject
from app.services.storage import new_project_dir
from app.services.pipeline import run_pipeline
from app.exporters.package_writer import write_export

root = Path(__file__).resolve().parents[1]
test_zip = root / "test_packages" / "complex_tableau_retail_migration_test_package.zip"
project_id, project_path = new_project_dir("path_regression")
project = MigrationProject(
    project_id=project_id,
    project_name=("complex_tableau_retail_migration_test_package_" * 5) + "windows_long_path_regression",
    workspace_path=str(project_path),
)
project = run_pipeline(project, [test_zip])
out = write_export(project)
assert out.exists(), out
with zipfile.ZipFile(out) as zf:
    names = zf.namelist()
    pbip = [n for n in names if n.endswith(".pbip")]
    assert len(pbip) == 1, pbip
    assert pbip[0].startswith("PBI/P"), pbip[0]
    assert max(map(len, names)) < 120, max(names, key=len)
print("PATH REGRESSION TEST PASSED")
print(out)
