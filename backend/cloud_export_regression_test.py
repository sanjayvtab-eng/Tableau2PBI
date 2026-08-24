from pathlib import Path
from tempfile import TemporaryDirectory

from app.models.schemas import SourceMapping
from app.services.path_parameter_engine import configure_mapping_path
from app.validators.pbip_integrity import _strict_excel_m


def test_cloud_workspace_path_is_not_serialized():
    with TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        source = workspace / "uploads" / "Academic_Data.xlsx"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"test")
        mapping = SourceMapping(
            source_id="s1",
            datasource="Academic_Data",
            original_connection_type="excel",
            target_connector="Excel",
            detected_source_path=str(source),
            target_file_path=None,
            table_name="Departments",
            parameter_values={"absolute_path": str(source)},
        )
        configure_mapping_path(mapping, workspace)
        assert mapping.resolved_powerbi_path is None
        assert "Cloud workspace path suppressed" in mapping.path_mode
        assert mapping.powerbi_path_parameter.endswith("_SourcePath")


def test_same_workbook_sheets_share_one_collision_safe_parameter():
    mapping_a = SourceMapping(
        source_id="a",
        datasource="Academic",
        original_connection_type="excel",
        target_connector="Excel",
        detected_source_path="Data/Academic_Data.xlsx",
        target_file_path="Data/Academic_Data.xlsx",
        table_name="Departments",
        parameter_values={},
    )
    mapping_b = SourceMapping(
        source_id="b",
        datasource="Academic",
        original_connection_type="excel",
        target_connector="Excel",
        detected_source_path="Data/Academic_Data.xlsx",
        target_file_path="Data/Academic_Data.xlsx",
        table_name="Courses",
        parameter_values={},
    )
    configure_mapping_path(mapping_a)
    configure_mapping_path(mapping_b)
    assert mapping_a.powerbi_path_parameter == mapping_b.powerbi_path_parameter


def test_excel_m_removes_silent_empty_table_and_first_sheet_fallbacks():
    source = '''let
    Workbook_Navigation = try Excel.Workbook(File.Contents(Academic_SourcePath), null, false) otherwise #table({"Name", "Data", "Item", "Kind", "Hidden"}, {}),
    Candidate_Objects = Table.SelectRows(Workbook_Navigation, each ([Kind] = "Table" or [Kind] = "Sheet")),
    Matching_Objects = Table.SelectRows(Candidate_Objects, each Text.Lower(Text.From([Item])) = Text.Lower("Departments") or Text.Lower(Text.From([Name])) = Text.Lower("Departments")),
    Source_Read = if Table.RowCount(Matching_Objects) > 0 then Matching_Objects{0}[Data] else if Table.RowCount(Candidate_Objects) > 0 then Candidate_Objects{0}[Data] else #table({}, {}),
    Promote_Source_Headers = try Table.PromoteHeaders(Source_Read, [PromoteAllScalars=true]) otherwise Source_Read,
    Safe_Convert_Values_To_Selected_Types = try Promote_Source_Headers otherwise #table({}, {})
in
    Safe_Convert_Values_To_Selected_Types
'''
    hardened = _strict_excel_m(source)
    assert "try Excel.Workbook" not in hardened
    assert "Candidate_Objects{0}[Data]" not in hardened
    assert "otherwise #table({}, {})" not in hardened
    assert "ExcelNavigation" in hardened
