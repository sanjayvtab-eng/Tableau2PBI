$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$testZip = Join-Path $root "test_packages\complex_tableau_retail_migration_test_package.zip"
Set-Location $backend
if (!(Test-Path ".venv\Scripts\python.exe")) { py -m venv .venv }
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$code = @"
from pathlib import Path
from app.models.schemas import MigrationProject
from app.services.storage import new_project_dir
from app.services.pipeline import run_pipeline
from app.exporters.package_writer import write_export
project_id, project_path = new_project_dir('self_test')
p = MigrationProject(project_id=project_id, project_name='self_test', workspace_path=str(project_path))
p = run_pipeline(p, [Path(r'$testZip')])
assert len(p.inventory) >= 50, f'Expected 50+ inventory rows, got {len(p.inventory)}'
assert len(p.source_mappings) >= 10, f'Expected 10+ source mappings, got {len(p.source_mappings)}'
assert len(p.migration_decisions) > 0, 'Expected migration decisions'
assert len(p.tde_analysis) >= 1, 'Expected TDE analysis for complex test package'
zip_path = write_export(p)
assert zip_path.exists(), 'Export ZIP not created'
print('SELF TEST PASSED')
print('Inventory:', len(p.inventory))
print('Source mappings:', len(p.source_mappings))
print('Migration decisions:', len(p.migration_decisions))
print('TDE analysis:', p.tde_analysis[0]['scenario'] if p.tde_analysis else 'none')
print('Health:', p.health_status)
print('Export:', zip_path)
"@
$env:PYTHONPATH = "."
python -c $code
