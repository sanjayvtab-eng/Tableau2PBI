from pathlib import Path
import tempfile
from app.models.schemas import MigrationProject, SourceMapping, DataPreview, DataProfileColumn
from app.services.pipeline import run_pipeline
from app.translators.m_generator import generate_m_query


def test_excel_navigates_to_data_object_before_column_typing():
    package = Path(__file__).resolve().parents[1] / 'test_packages' / 'complex_tableau_tde_retail_migration_test_package_v10.zip'
    with tempfile.TemporaryDirectory(prefix='t2pbi_schema_align_') as td:
        project = run_pipeline(MigrationProject(project_id='schema_align', project_name='Schema Align', workspace_path=td), [package])
        target = next(t for t in project.semantic_tables if t.name.casefold() == 'sales_targets')
        assert 'Workbook_Navigation = Excel.Workbook' in target.m_query
        assert 'Candidate_Objects = Table.SelectRows' in target.m_query
        assert 'Source_Read = if Table.RowCount' in target.m_query
        assert 'Table.PromoteHeaders(Source_Read' in target.m_query
        assert 'Table.TransformColumnTypes' in target.m_query
        assert '"Region"' in target.m_query


def test_unresolved_database_source_preserves_declared_schema_without_credentials():
    mapping = SourceMapping(source_id='oracle1', datasource='Territory', original_connection_type='oracle', target_connector='Oracle', table_name='Territory')
    expected = [
        {'name':'Territory ID','source_name':'Territory ID','data_type':'Text'},
        {'name':'Region','source_name':'Region','data_type':'Text'},
    ]
    m = generate_m_query('Territory', mapping, None, expected_columns=expected)
    assert '#table(type table [' in m
    assert '#"Territory ID" = text' in m
    assert '#"Region" = text' in m
    assert 'Manual source placeholder' in m


def test_readable_duplicate_business_source_wins_over_unresolved_placeholder():
    package = Path(__file__).resolve().parents[1] / 'test_packages' / 'complex_tableau_tde_retail_migration_test_package_v10.zip'
    with tempfile.TemporaryDirectory(prefix='t2pbi_duplicate_source_') as td:
        project = run_pipeline(MigrationProject(project_id='dup_source', project_name='Dup Source', workspace_path=td), [package])
        customers = [t for t in project.semantic_tables if t.name.casefold() == 'customers']
        assert len(customers) == 1
        assert customers[0].source_id.startswith('inventory_data_customers_csv')
        assert {c['source_name'] for c in customers[0].columns} == {'Customer ID','Customer Name','Segment','Region','State'}


if __name__ == '__main__':
    test_excel_navigates_to_data_object_before_column_typing()
    test_unresolved_database_source_preserves_declared_schema_without_credentials()
    test_readable_duplicate_business_source_wins_over_unresolved_placeholder()
    print('schema_alignment_regression_test: PASS')
