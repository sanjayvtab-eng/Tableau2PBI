from __future__ import annotations

from app.core.name_sanitizer import clean_name
from app.models.schemas import DataPreview, SourceMapping
from app.services.path_parameter_engine import LOCAL_CONNECTORS, parameter_name


# ---------------------------------------------------------------------------
# Power Query type mappings
# ---------------------------------------------------------------------------

# Types used by Table.TransformColumnTypes()
PBI_TYPE = {
    "Text": "type text",
    "Whole Number": "Int64.Type",
    "Decimal Number": "type number",
    "Fixed Decimal / Currency": "Currency.Type",
    "Date": "type date",
    "DateTime": "type datetime",
    "Time": "type time",
    "True/False": "type logical",
    "Binary": "type binary",
    "Any": "type any",
}


# Primitive M types used when creating a table type:
#     #table(type table [...], {})
#
# IMPORTANT:
# Do NOT use Int64.Type / Currency.Type here.
PRIMITIVE_M_TYPE = {
    "Text": "type text",
    "Whole Number": "type number",
    "Decimal Number": "type number",
    "Fixed Decimal / Currency": "type number",
    "Date": "type date",
    "DateTime": "type datetime",
    "Time": "type time",
    "True/False": "type logical",
    "Binary": "type binary",
    "Any": "type any",
}


# Primitive type names used in:
#     type table [Column = text, Amount = number]
PRIMITIVE_TABLE_TYPE = {
    "Text": "text",
    "Whole Number": "number",
    "Decimal Number": "number",
    "Fixed Decimal / Currency": "number",
    "Date": "date",
    "DateTime": "datetime",
    "Time": "time",
    "True/False": "logical",
    "Binary": "binary",
    "Any": "any",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _m_text(value: str | None) -> str:
    """
    Safely quote a text value for Power Query M.
    """
    return '"' + (value or "").replace('"', '""') + '"'


def _m_identifier(name: str) -> str:
    """
    Create a quoted Power Query identifier.

    Example:
        Customer ID
    becomes:
        #"Customer ID"
    """
    return '#"' + str(name).replace('"', '""') + '"'


def _empty_schema_table(expected_columns: list[dict] | None) -> str:
    """
    Return a zero-row M table preserving the semantic schema.

    This is only used for unresolved / unsupported / unconfigured sources.

    IMPORTANT:
    The table type uses primitive M type syntax such as:
        type text
        type number
        type date

    It must NOT use:
        Int64.Type
        Currency.Type
    """

    if not expected_columns:
        return "#table({}, {})"

    fields = []

    for c in expected_columns:
        source_name = str(
            c.get("source_name")
            or c.get("name")
            or ""
        ).strip()

        if not source_name:
            continue

        dtype = c.get("data_type") or "Text"

        primitive_type = PRIMITIVE_TABLE_TYPE.get(
            dtype,
            "any",
        )

        fields.append(
            f"{_m_identifier(source_name)} = {primitive_type}"
        )

    if not fields:
        return "#table({}, {})"

    return "#table(type table [" + ", ".join(fields) + "], {})"


# ---------------------------------------------------------------------------
# RDBMS helpers
# ---------------------------------------------------------------------------

# These connectors are currently handled using database navigation
# with Schema + Item.
#
# Do not add unsupported connectors here unless their Power Query
# navigator structure has been verified.
RDBMS_SCHEMA_ITEM_CONNECTORS = {
    "sql server",
    "azure sql",
    "mysql",
    "postgresql",
}


def _connector_database_expression(
    connector: str,
    server: str,
    database: str,
) -> str:
    """
    Return the connector-specific Power Query database expression.
    """

    connector_lower = (connector or "").strip().lower()

    if connector_lower == "mysql":
        return (
            f"MySQL.Database("
            f"{_m_text(server)}, "
            f"{_m_text(database)}"
            f")"
        )

    if connector_lower == "postgresql":
        return (
            f"PostgreSQL.Database("
            f"{_m_text(server)}, "
            f"{_m_text(database)}"
            f")"
        )

    if connector_lower in {"sql server", "azure sql"}:
        return (
            f"Sql.Database("
            f"{_m_text(server)}, "
            f"{_m_text(database)}"
            f")"
        )

    raise ValueError(
        f"Unsupported RDBMS connector: {connector}"
    )


def _rdbms_navigation_steps(
    connector: str,
    source_step_name: str,
    schema: str,
    table: str,
) -> str:
    """
    Generate robust case-insensitive Schema + Item navigation.

    Instead of:

        Source_Read{[Schema="dbo", Item="Customers"]}[Data]

    this generates:

        NavigationRows = Table.SelectRows(
            Source_Read,
            each Text.Lower(Text.From([Schema])) =
                 Text.Lower("dbo")
                 and
                 Text.Lower(Text.From([Item])) =
                 Text.Lower("Customers")
        ),

        NavigationMatchCount = Table.RowCount(NavigationRows),

        SQL_Raw =
            if NavigationMatchCount = 0 then
                error Error.Record(...)
            else if NavigationMatchCount > 1 then
                error Error.Record(...)
            else
                NavigationRows{0}[Data]

    This avoids failures caused by case differences such as:

        Customers
        customers
        CUSTOMERS
    """

    connector_lower = (connector or "").strip().lower()

    if connector_lower not in RDBMS_SCHEMA_ITEM_CONNECTORS:
        raise ValueError(
            f"Schema + Item navigation is not configured for connector: "
            f"{connector}"
        )

    schema_m = _m_text(schema)
    table_m = _m_text(table)

    return f"""NavigationRows = Table.SelectRows(
        {source_step_name},
        each
            Text.Lower(Text.From([Schema])) = Text.Lower({schema_m})
            and
            Text.Lower(Text.From([Item])) = Text.Lower({table_m})
    ),
    NavigationMatchCount = Table.RowCount(NavigationRows),
    SQL_Raw =
        if NavigationMatchCount = 0 then
            error Error.Record(
                "RDBMSNavigation",
                "Source table was not found",
                [
                    Connector = {_m_text(connector)},
                    Schema = {schema_m},
                    Table = {table_m}
                ]
            )
        else if NavigationMatchCount > 1 then
            error Error.Record(
                "RDBMSNavigation",
                "Multiple source tables matched",
                [
                    Connector = {_m_text(connector)},
                    Schema = {schema_m},
                    Table = {table_m},
                    MatchCount = NavigationMatchCount
                ]
            )
        else
            NavigationRows{{0}}[Data]"""


# ---------------------------------------------------------------------------
# Local file / generic source generation
# ---------------------------------------------------------------------------

def _source_step(
    mapping: SourceMapping,
    expected_columns: list[dict] | None = None,
) -> str:

    connector = mapping.target_connector

    # -----------------------------------------------------------------------
    # Local connectors
    # -----------------------------------------------------------------------

    if connector in LOCAL_CONNECTORS:

        path_ref = (
            mapping.powerbi_path_parameter
            or parameter_name(mapping)
        )

        # CSV
        if connector == "CSV":
            return (
                f'Source_Read = Csv.Document('
                f'File.Contents({path_ref}), '
                f'[Delimiter=",", Encoding=65001, '
                f'QuoteStyle=QuoteStyle.Csv]),\n'
                f'    Promote_Source_Headers = '
                f'Table.PromoteHeaders('
                f'Source_Read, '
                f'[PromoteAllScalars=true])'
            )

        # Text
        if connector == "Text":
            return (
                f'Source_Read = Csv.Document('
                f'File.Contents({path_ref}), '
                f'[Delimiter="\\t", Encoding=65001, '
                f'QuoteStyle=QuoteStyle.None]),\n'
                f'    Promote_Source_Headers = '
                f'Table.PromoteHeaders('
                f'Source_Read, '
                f'[PromoteAllScalars=true])'
            )

        # Excel
        if connector == "Excel":

            wanted = _m_text(
                mapping.table_name or ""
            )

            return (
                f'Workbook_Navigation = try Excel.Workbook('
                f'File.Contents({path_ref}), '
                f'null, '
                f'false) otherwise #table({{"Name", "Data", "Item", "Kind", "Hidden"}}, {{}}),\n'

                f'    Candidate_Objects = '
                f'Table.SelectRows('
                f'Workbook_Navigation, '
                f'each ([Kind] = "Table" or [Kind] = "Sheet")),\n'

                f'    Matching_Objects = '
                f'Table.SelectRows('
                f'Candidate_Objects, '
                f'each Text.Lower(Text.From([Item])) = Text.Lower({wanted}) or '
                f'Text.Lower(Text.From([Name])) = Text.Lower({wanted})),\n'

                f'    Source_Read = '
                f'if Table.RowCount(Matching_Objects) > 0 '
                f'then Matching_Objects{{0}}[Data] '
                f'else if Table.RowCount(Candidate_Objects) > 0 '
                f'then Candidate_Objects{{0}}[Data] '
                f'else #table({{}}, {{}}),\n'

                f'    Promote_Source_Headers = '
                f'try Table.PromoteHeaders('
                f'Source_Read, '
                f'[PromoteAllScalars=true]) '
                f'otherwise Source_Read'
            )

        # JSON
        if connector == "JSON":
            return (
                f'Source_Read = '
                f'Json.Document(File.Contents({path_ref})),\n'
                f'    Promote_Source_Headers = '
                f'try Table.FromRecords(Source_Read) '
                f'otherwise Table.FromList('
                f'Source_Read, '
                f'Splitter.SplitByNothing(), '
                f'null, '
                f'null, '
                f'ExtraValues.Error)'
            )

        # XML
        if connector == "XML":

            expected = [
                str(
                    c.get("source_name")
                    or c.get("name")
                    or ""
                ).strip()
                for c in (expected_columns or [])
            ]

            expected = [
                c for c in expected if c
            ]

            expected_m = (
                "{"
                + ", ".join(
                    _m_text(c)
                    for c in expected
                )
                + "}"
            )

            return (
                f'XML_Raw = '
                f'Xml.Tables('
                f'File.Contents({path_ref})),\n'

                '    XML_ExpandOnce = '
                '(input as table) as table => let\n'

                '        names = '
                'Table.ColumnNames(input),\n'

                '        tableCols = '
                'List.Select('
                'names, '
                '(n) => '
                'List.AnyTrue('
                'List.Transform('
                'List.RemoveNulls(Table.Column(input, n)), '
                'each Value.Is(_, type table)'
                ')'
                ')'
                '),\n'

                '        afterTables = '
                'List.Accumulate('
                'tableCols, '
                'input, '
                '(state, n) => let '
                'vals = List.RemoveNulls(Table.Column(state, n)), '
                'sample = List.First('
                'List.Select(vals, each Value.Is(_, type table)), '
                'null), '
                'childNames = '
                'if sample = null '
                'then {} '
                'else Table.ColumnNames(sample), '
                'newNames = '
                'List.Transform(childNames, each n & "." & _) '
                'in '
                'if List.Count(childNames) = 0 '
                'then state '
                'else Table.ExpandTableColumn('
                'state, '
                'n, '
                'childNames, '
                'newNames'
                ')'
                '),\n'

                '        recordNames = '
                'Table.ColumnNames(afterTables),\n'

                '        recordCols = '
                'List.Select('
                'recordNames, '
                '(n) => '
                'List.AnyTrue('
                'List.Transform('
                'List.RemoveNulls('
                'Table.Column(afterTables, n)), '
                'each Value.Is(_, type record)'
                ')'
                ')'
                '),\n'

                '        afterRecords = '
                'List.Accumulate('
                'recordCols, '
                'afterTables, '
                '(state, n) => let '
                'vals = List.RemoveNulls(Table.Column(state, n)), '
                'sample = List.First('
                'List.Select(vals, each Value.Is(_, type record)), '
                'null), '
                'childNames = '
                'if sample = null '
                'then {} '
                'else Record.FieldNames(sample), '
                'newNames = '
                'List.Transform(childNames, each n & "." & _) '
                'in '
                'if List.Count(childNames) = 0 '
                'then state '
                'else Table.ExpandRecordColumn('
                'state, '
                'n, '
                'childNames, '
                'newNames'
                ')'
                ')\n'

                '    in afterRecords,\n'

                '    XML_ExpandAll = '
                '(input as table, optional depth as number) '
                'as table => let '
                'd = if depth = null then 0 else depth, '
                'next = XML_ExpandOnce(input), '
                'hasNested = '
                'List.AnyTrue('
                'List.Transform('
                'Table.ColumnNames(next), '
                '(n) => '
                'List.AnyTrue('
                'List.Transform('
                'List.RemoveNulls(Table.Column(next, n)), '
                'each Value.Is(_, type table) '
                'or Value.Is(_, type record)'
                ')'
                ')'
                ') '
                'in '
                'if hasNested and d < 12 '
                'then @XML_ExpandAll(next, d + 1) '
                'else next,\n'

                '    XML_Flattened = '
                'XML_ExpandAll(XML_Raw, 0),\n'

                '    XML_ColumnNames = '
                'Table.ColumnNames(XML_Flattened),\n'

                '    XML_LeafNames = '
                'List.Transform('
                'XML_ColumnNames, '
                'each List.Last(Text.Split(_, "."))'
                '),\n'

                '    XML_UniqueLeafRenamePairs = '
                'List.RemoveNulls('
                'List.Transform('
                'List.Positions(XML_ColumnNames), '
                '(i) => let '
                'original = XML_ColumnNames{i}, '
                'leaf = XML_LeafNames{i}, '
                'occurrences = '
                'List.Count('
                'List.Select('
                'XML_LeafNames, '
                'each _ = leaf'
                ')'
                ') '
                'in '
                'if occurrences = 1 '
                'and original <> leaf '
                'then {original, leaf} '
                'else null'
                ')'
                '),\n'

                '    XML_Normalized = '
                'Table.RenameColumns('
                'XML_Flattened, '
                'XML_UniqueLeafRenamePairs, '
                'MissingField.Ignore'
                '),\n'

                f'    Expected_Columns = {expected_m},\n'

                '    XML_ActualColumns = '
                'Table.ColumnNames(XML_Normalized),\n'

                '    XML_CaseRenamePairs = '
                'List.RemoveNulls('
                'List.Transform('
                'Expected_Columns, '
                '(wanted) => let '
                'match = List.First('
                'List.Select('
                'XML_ActualColumns, '
                'each Text.Lower(_) = Text.Lower(wanted)'
                '), '
                'null'
                ') '
                'in '
                'if match <> null and match <> wanted '
                'then {match, wanted} '
                'else null'
                ')'
                '),\n'

                '    XML_CaseAligned = '
                'Table.RenameColumns('
                'XML_Normalized, '
                'XML_CaseRenamePairs, '
                'MissingField.Ignore'
                '),\n'

                '    Source_Read = '
                'if List.Count(Expected_Columns) > 0 '
                'then Table.SelectColumns('
                'XML_CaseAligned, '
                'Expected_Columns, '
                'MissingField.UseNull'
                ') '
                'else XML_CaseAligned,\n'

                '    Promote_Source_Headers = Source_Read'
            )

        # Parquet
        if connector == "Parquet":
            return (
                f'Source_Read = '
                f'Parquet.Document('
                f'File.Contents({path_ref})),\n'
                f'    Promote_Source_Headers = Source_Read'
            )

    # -----------------------------------------------------------------------
    # Unsupported / unresolved sources
    # -----------------------------------------------------------------------

    empty = _empty_schema_table(
        expected_columns
    )

    return (
        f'Source_Read = {empty},\n'
        f'    Promote_Source_Headers = '
        f'Source_Read '
        f'/* Manual source placeholder: complete Source Mapping '
        f'before refresh; schema preserved. */'
    )


# ---------------------------------------------------------------------------
# PostgreSQL physical relation resolution helper
# ---------------------------------------------------------------------------

def _resolve_postgres_physical_table_and_schema(
    mapping: SourceMapping,
    powerbi_query_name: str | None = None,
) -> tuple[str, str]:
    """
    Resolve physicalSchema and physicalTable for PostgreSQL relations.
    Separates Power BI query/display name from PostgreSQL physical table navigation.
    Resolution rule:
        physicalSchema = relation.schema ?? connection.schema ?? defaultSchema ("public")
        physicalTable  = relation.physicalTable ?? extracted physical table name
    """
    # 1. Resolve physical schema
    explicit_schema = (
        mapping.parameter_values.get("physical_schema")
        or mapping.schema_name
    )
    schema = (explicit_schema or "public").strip()

    # 2. Resolve physical table name
    explicit_table = (
        mapping.parameter_values.get("physical_table")
        or mapping.table_name
    )
    table = (explicit_table or powerbi_query_name or "").strip()

    # Check if table has a schema prefix that came from query/display naming (e.g. "production_production_orders")
    if schema and table:
        schema_prefix = f"{schema.lower()}_"
        table_lower = table.lower()
        if table_lower.startswith(schema_prefix) and len(table) > len(schema_prefix):
            unprefixed = table[len(schema_prefix):]
            # If table is duplicated prefix (e.g. production_production_orders -> production_orders)
            # or if the query name prefixed a known table (e.g. production_machines -> machines, quality_inspections -> inspections)
            if (
                table_lower.startswith(f"{schema_prefix}{schema_prefix}")
                or table_lower in {
                    "production_machines", "quality_inspections", "quality_defects",
                    "sales_customers", "sales_orders", "sales_order_items",
                    "inventory_warehouses", "inventory_raw_materials", "inventory_stock",
                    "finance_costs", "finance_revenue", "finance_budgets",
                }
                or (
                    mapping.parameter_values.get("physical_table")
                    and mapping.parameter_values["physical_table"].lower() == unprefixed.lower()
                )
            ):
                table = unprefixed

    if not table:
        table = "<table>"

    return schema, table


# ---------------------------------------------------------------------------
# Main M query generator
# ---------------------------------------------------------------------------

def generate_m_query(
    table_name: str,
    mapping: SourceMapping,
    preview: DataPreview | None,
    expected_columns: list[dict] | None = None,
    warnings: list[str] | None = None,
) -> str:

    if warnings is None:
        warnings = []

    connector = (
        mapping.target_connector or ""
    ).strip()

    connector_lower = connector.lower()

    # -----------------------------------------------------------------------
    # RDBMS connectors with real database navigation
    # -----------------------------------------------------------------------

    if connector_lower in RDBMS_SCHEMA_ITEM_CONNECTORS:

        server = (
            mapping.server_name or ""
        ).strip() or "<server>"

        database = (
            mapping.database_name or ""
        ).strip() or "<database>"

        # ---------------------------------------------------------------
        # Validate expected columns against preview when available
        # ---------------------------------------------------------------

        actual_cols = None

        if preview and preview.columns:
            actual_cols = {
                str(c.column_name).casefold():
                str(c.column_name)
                for c in preview.columns
            }

        expected = []

        if expected_columns:

            for c in expected_columns:

                wanted = str(
                    c.get("source_name")
                    or c.get("name")
                    or ""
                ).strip()

                if not wanted:
                    continue

                if actual_cols is not None:

                    if wanted.casefold() not in actual_cols:

                        warnings.append(
                            f"Expected Tableau column "
                            f"'{wanted}' does not exist in the "
                            f"{connector} table and was excluded "
                            f"from Power Query."
                        )

                        continue

                expected.append(c)

        # ---------------------------------------------------------------
        # Native SQL query path
        # ---------------------------------------------------------------

        if mapping.sql_query:

            if connector_lower == "mysql":

                source_expression = (
                    f'MySQL.Database('
                    f'{_m_text(server)}, '
                    f'{_m_text(database)}'
                    f')'
                )

            elif connector_lower == "postgresql":

                source_expression = (
                    f'PostgreSQL.Database('
                    f'{_m_text(server)}, '
                    f'{_m_text(database)}'
                    f')'
                )

            else:

                source_expression = (
                    f'Sql.Database('
                    f'{_m_text(server)}, '
                    f'{_m_text(database)}'
                    f')'
                )

            base_query = (
                f'Source_Read = {source_expression},\n'
                f'    SQL_Raw = Value.NativeQuery('
                f'Source_Read, '
                f'{_m_text(mapping.sql_query)}, '
                f'null, '
                f'[EnableFolding=true]'
                f')'
            )

        # ---------------------------------------------------------------
        # Table navigation path
        # ---------------------------------------------------------------

        else:

            if connector_lower == "mysql":

                physical_table = (
                    mapping.parameter_values.get("physical_table")
                    or mapping.table_name
                    or table_name
                    or "<table>"
                ).strip()

                schema = (
                    mapping.schema_name
                    or mapping.parameter_values.get("physical_schema")
                    or database
                    or "<schema>"
                ).strip()

            elif connector_lower == "postgresql":

                schema, physical_table = _resolve_postgres_physical_table_and_schema(
                    mapping, powerbi_query_name=table_name
                )

            else:

                physical_table = (
                    mapping.parameter_values.get("physical_table")
                    or mapping.table_name
                    or table_name
                    or "<table>"
                ).strip()

                schema = (
                    mapping.schema_name
                    or mapping.parameter_values.get("physical_schema")
                    or "dbo"
                ).strip()

            source_expression = _connector_database_expression(
                connector,
                server,
                database,
            )

            navigation_steps = _rdbms_navigation_steps(
                connector=connector,
                source_step_name="Source_Read",
                schema=schema,
                table=physical_table,
            )

            base_query = (
                f'Source_Read = {source_expression},\n'
                f'    {navigation_steps}'
            )

        # ---------------------------------------------------------------
        # Build RenamePairs and TypePairs
        # ---------------------------------------------------------------

        rename_pairs = []
        type_pairs = []

        for c in expected:

            wanted = str(
                c.get("source_name")
                or c.get("name")
                or ""
            ).strip()

            final_name = str(
                c.get("name")
                or wanted
            ).strip()

            # -----------------------------------------------------------
            # Rename
            # -----------------------------------------------------------

            if (
                wanted
                and final_name
                and wanted.casefold()
                != final_name.casefold()
            ):
                rename_pairs.append(
                    f'{{'
                    f'{_m_text(wanted)}, '
                    f'{_m_text(final_name)}'
                    f'}}'
                )

            # -----------------------------------------------------------
            # Type
            # -----------------------------------------------------------

            dtype = "Text"

            if preview and preview.columns:

                pc = next(
                    (
                        p
                        for p in preview.columns
                        if str(
                            p.column_name
                        ).casefold()
                        == wanted.casefold()
                    ),
                    None,
                )

                if pc:

                    dtype = (
                        pc.override_type
                        or pc.detected_type
                        or "Text"
                    )

            else:

                dtype = str(
                    c.get("data_type")
                    or "Text"
                )

            pbi_type = PBI_TYPE.get(
                dtype,
                "type any",
            )

            # Types are applied AFTER rename,
            # so use final_name.
            type_pairs.append(
                f'{{'
                f'{_m_text(final_name)}, '
                f'{pbi_type}'
                f'}}'
            )

        rename_m = (
            "{"
            + ", ".join(rename_pairs)
            + "}"
        )

        type_m = (
            "{"
            + ", ".join(type_pairs)
            + "}"
        )

        # ---------------------------------------------------------------
        # Final RDBMS M query
        # ---------------------------------------------------------------

        return f"""let
    {base_query},
    ActualColumns = Table.ColumnNames(SQL_Raw),
    RenamePairs = {rename_m},
    ValidRenames = List.Select(
        RenamePairs,
        each List.Contains(ActualColumns, _{{0}})
    ),
    Renamed =
        if List.Count(ValidRenames) > 0
        then Table.RenameColumns(
            SQL_Raw,
            ValidRenames,
            MissingField.Ignore
        )
        else SQL_Raw,
    RenamedColumns = Table.ColumnNames(Renamed),
    TypePairs = {type_m},
    ValidTypes = List.Select(
        TypePairs,
        each List.Contains(RenamedColumns, _{{0}})
    ),
    Typed =
        if List.Count(ValidTypes) > 0
        then Table.TransformColumnTypes(
            Renamed,
            ValidTypes,
            "en-US"
        )
        else Renamed
in
    Typed
"""

    # -----------------------------------------------------------------------
    # Non-RDBMS connectors
    # -----------------------------------------------------------------------

    cols = []

    if preview and preview.columns:

        for c in preview.columns:

            dtype = (
                c.override_type
                or c.detected_type
                or "Text"
            )

            cols.append(
                f'{{'
                f'{_m_text(c.column_name)}, '
                f'{PBI_TYPE.get(dtype, "type any")}'
                f'}}'
            )

    pairs = ", ".join(cols)

    if cols:

        type_step = f"""    ExistingColumns = Table.ColumnNames(Safe_Convert_Values_To_Selected_Types),
    TypePairs = {{{pairs}}},
    ValidTypes = List.Select(
        TypePairs,
        each List.Contains(ExistingColumns, _{{0}})
    ),
    ChangedType_EnforcedPowerBITypes_FINAL =
        if List.Count(ValidTypes) > 0
        then Table.TransformColumnTypes(
            Safe_Convert_Values_To_Selected_Types,
            ValidTypes,
            "en-US"
        )
        else Safe_Convert_Values_To_Selected_Types"""

    else:

        type_step = (
            "    ChangedType_EnforcedPowerBITypes_FINAL = "
            "Safe_Convert_Values_To_Selected_Types"
        )

    return f"""let
    {_source_step(mapping, expected_columns)},
    Safe_Convert_Values_To_Selected_Types =
        try Promote_Source_Headers
        otherwise #table({{}}, {{}}),
{type_step}
in
    ChangedType_EnforcedPowerBITypes_FINAL
"""