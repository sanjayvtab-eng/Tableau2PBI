from pathlib import Path
import tempfile
from app.models.schemas import MigrationProject, SemanticTable
from app.services.pipeline import run_pipeline, _dedupe_semantic_measures
from app.exporters.package_writer import _model_bim


def test_package_json_xml_not_promoted_when_unreferenced():
    package = Path(__file__).resolve().parents[1] / 'test_packages' / 'complex_tableau_tde_retail_migration_test_package_v10.zip'
    with tempfile.TemporaryDirectory(prefix='t2pbi_semantic_cleanup_') as td:
        project = MigrationProject(project_id='semantic_cleanup', project_name='Semantic Cleanup', workspace_path=td)
        project = run_pipeline(project, [package])
        semantic = {t.name.casefold() for t in project.semantic_tables}
        assert 'discount_policy' not in semantic
        assert 'territory_mapping' not in semantic
        assert not any(m.target_connector in {'JSON', 'XML'} for m in project.source_mappings)


def test_duplicate_measure_names_are_collapsed_model_wide():
    project = MigrationProject(project_id='measure_cleanup', project_name='Measure Cleanup', workspace_path='.')
    project.semantic_tables = [
        SemanticTable(name='Sales', measures=[{'name':'Total Sales','expression':"SUM('Sales'[Amount])",'confidence':0.95}]),
        SemanticTable(name='Orders', measures=[{'name':'total sales','expression':"SUM('Orders'[Amount])",'confidence':0.80}]),
    ]
    project.semantic_tables = _dedupe_semantic_measures(project, project.semantic_tables)
    assert sum(len(t.measures) for t in project.semantic_tables) == 1
    model = _model_bim(project)['model']
    assert sum(len(t.get('measures', [])) for t in model['tables']) == 1


if __name__ == '__main__':
    test_package_json_xml_not_promoted_when_unreferenced()
    test_duplicate_measure_names_are_collapsed_model_wide()
    print('semantic_cleanup_regression_test: PASS')
