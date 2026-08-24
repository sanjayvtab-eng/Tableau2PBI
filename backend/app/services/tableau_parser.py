from __future__ import annotations
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from app.core.name_sanitizer import clean_name
from app.core.tableau_xml import parse_xml_file, iter_by_tag, tag_name, first_attr, text_of
from app.models.schemas import (
    TableauCalculation,
    TableauConnection,
    TableauDashboard,
    TableauDataSource,
    TableauField,
    TableauParameter,
    TableauRelation,
    TableauStory,
    TableauWorksheet,
)
from app.services.migration_strategy import is_tableau_generated_field

FIELD_REF_RE = re.compile(r"\[([^\]]+)\]")


def _id(*parts: str | None) -> str:
    joined = "|".join([p or "" for p in parts])
    return hashlib.sha1(joined.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _extract_formula(column: ET.Element) -> str | None:
    for calc in column.iter():
        if tag_name(calc) == "calculation":
            return first_attr(calc, "formula", default=text_of(calc))
    return None


def _field_from_column(column: ET.Element, datasource_name: str | None) -> TableauField:
    name = first_attr(column, "caption", "name", default="Unnamed Field") or "Unnamed Field"
    caption = first_attr(column, "caption")
    formula = _extract_formula(column)
    return TableauField(
        name=clean_name(name.strip("[]")),
        caption=caption,
        datatype=first_attr(column, "datatype", "type"),
        role=first_attr(column, "role"),
        aggregation=first_attr(column, "aggregation"),
        formula=formula,
        is_calculated=bool(formula),
        is_parameter=(first_attr(column, "param-domain-type") is not None or first_attr(column, "role") == "parameter"),
        datasource=datasource_name,
    )


def _connection_from_elem(elem: ET.Element, datasource_name: str) -> TableauConnection:
    props = dict(elem.attrib)
    nested = next((x for x in elem.iter() if tag_name(x) == "connection" and x is not elem), None)
    if nested is not None:
        props.update(nested.attrib)
    conn_class = props.get("class") or props.get("connection-class") or props.get("type") or "Unknown"
    server = props.get("server") or props.get("host")
    db = props.get("dbname") or props.get("database") or props.get("catalog")
    local_path = props.get("filename") or props.get("path")
    schema = props.get("schema")
    table = props.get("table")
    auth = props.get("authentication") or props.get("authentication-mode")
    return TableauConnection(
        id=_id(datasource_name, conn_class, server, db, local_path, table),
        datasource=datasource_name,
        connection_type=conn_class,
        server=server,
        database=db,
        schema_name=schema,
        table_name=table,
        local_file_path=local_path,
        authentication_mode=auth,
        properties=props,
    )


def _relation_from_elem(elem: ET.Element, datasource_name: str) -> TableauRelation:
    name = first_attr(elem, "name", "table", default="Relation") or "Relation"
    relation_type = first_attr(elem, "type", default="table") or "table"
    custom_sql = text_of(elem) if relation_type.lower() in {"text", "custom_sql", "customsql"} else None
    if not custom_sql:
        for child in list(elem):
            if tag_name(child) in {"relation", "customsql"} and text_of(child):
                custom_sql = text_of(child)
    clauses: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    for c in elem.iter():
        t = tag_name(c)
        if t in {"clause", "expression"}:
            clauses.append(dict(c.attrib) | ({"text": text_of(c)} if text_of(c) else {}))
        if t == "relation" and c is not elem:
            children.append({"name": first_attr(c, "name", "table"), "type": first_attr(c, "type"), "table": first_attr(c, "table")})
    return TableauRelation(
        id=_id(datasource_name, name, first_attr(elem, "table"), relation_type),
        datasource=datasource_name,
        connection_name=first_attr(elem, "connection"),
        name=clean_name(name.strip("[]")),
        relation_type=relation_type,
        table=first_attr(elem, "table"),
        join_type=first_attr(elem, "join", "join-type", "type") if relation_type.lower() == "join" else None,
        clauses=clauses,
        custom_sql=custom_sql,
        children=children,
    )


def parse_workbook_or_datasource(path: Path) -> dict[str, Any]:
    root = parse_xml_file(path)
    workbook_name = first_attr(root, "name", default=path.stem) or path.stem
    version = first_attr(root, "version", "source-build", default="Unknown")
    datasources: list[TableauDataSource] = []
    calculations: list[TableauCalculation] = []
    parameters: list[TableauParameter] = []

    datasource_nodes = [d for d in iter_by_tag(root, "datasource")]
    if tag_name(root) == "datasource":
        datasource_nodes = [root]

    for ds in datasource_nodes:
        ds_name = first_attr(ds, "caption", "name", "formatted-name")
        if not ds_name:
            ds_name = path.stem if tag_name(root) == "datasource" else "Datasource"
        ds_name_clean = clean_name(ds_name.strip("[]"), "Datasource")
        tds = TableauDataSource(
            id=_id(str(path), ds_name_clean),
            name=ds_name_clean,
            caption=first_attr(ds, "caption"),
            source_kind="Published" if first_attr(ds, "published") else "Embedded",
            extract_or_live="Extract" if any(tag_name(x) == "extract" for x in ds.iter()) else "Live/Unknown",
        )
        processed_conns = set()
        for conn in [c for c in ds.iter() if tag_name(c) in {"connection", "named-connection"}]:
            if conn in processed_conns:
                continue
            if tag_name(conn) == "named-connection":
                tds.connections.append(_connection_from_elem(conn, ds_name_clean))
                for child in conn.iter():
                    processed_conns.add(child)
            elif first_attr(conn, "class") != "federated":
                tds.connections.append(_connection_from_elem(conn, ds_name_clean))
        # Some packaged workbooks store relations under connection nodes.
        for rel in [r for r in ds.iter() if tag_name(r) == "relation"]:
            tds.relations.append(_relation_from_elem(rel, ds_name_clean))
        field_provenance = {}
        for map_node in [m for m in ds.iter() if tag_name(m) == "map"]:
            key = first_attr(map_node, "key")
            val = first_attr(map_node, "value")
            if key and val:
                parts = [p.strip("[] \t\r\n") for p in val.split("].[") if p.strip()]
                if len(parts) >= 2:
                    table_part = parts[-2].split(".")[-1].strip("[] \t\r\n\"'")
                    field_provenance[clean_name(key.strip("[]"))] = clean_name(table_part)
                elif len(parts) == 1 and "." in parts[0]:
                    subparts = parts[0].split(".")
                    if len(subparts) >= 2:
                        field_provenance[clean_name(key.strip("[]"))] = clean_name(subparts[-2])

        for mr in [r for r in ds.iter() if tag_name(r) == "metadata-record"]:
            if first_attr(mr, "class") == "column":
                parent = ""
                local_name = ""
                remote_name = ""
                for child in mr:
                    if tag_name(child) == "parent-name" and text_of(child):
                        parent = text_of(child).strip("[]")
                    elif tag_name(child) == "local-name" and text_of(child):
                        local_name = text_of(child).strip("[]")
                    elif tag_name(child) == "remote-name" and text_of(child):
                        remote_name = text_of(child).strip("[]")
                if parent:
                    parent_clean = clean_name(parent.split(".")[-1])
                    if local_name:
                        field_provenance[clean_name(local_name)] = parent_clean
                    if remote_name:
                        field_provenance[clean_name(remote_name)] = parent_clean

        table_relations = [r.name for r in tds.relations if r.relation_type == "table" and r.name]
        if not field_provenance and len(table_relations) > 1:
            rel_idx = 0
            current_rel = table_relations[0]
            for col in [c for c in ds.iter() if tag_name(c) == "column"]:
                raw_name = first_attr(col, "name", default="")
                clean_col = clean_name(raw_name.strip("[]"))
                if not clean_col:
                    continue
                if rel_idx + 1 < len(table_relations):
                    next_r = table_relations[rel_idx + 1]
                    next_stem = next_r.rstrip("s").lower()
                    clean_lower = clean_col.lower()
                    if (
                        clean_lower == f"{next_stem}id"
                        or clean_lower == f"{next_r.lower()}id"
                        or (next_r.lower() == "salestarget" and clean_lower == "targetid")
                        or clean_lower.startswith(next_stem)
                        or clean_lower.startswith(next_r.lower())
                    ):
                        rel_idx += 1
                        current_rel = table_relations[rel_idx]
                field_provenance[clean_col] = current_rel
                    
        for col in [c for c in ds.iter() if tag_name(c) == "column"]:
            field = _field_from_column(col, ds_name_clean)
            if field.name in field_provenance:
                field.provenance = field_provenance[field.name]
            if (field.name, field.provenance) not in {(f.name, f.provenance) for f in tds.fields}:
                tds.fields.append(field)
            if field.is_parameter:
                parameters.append(TableauParameter(name=field.name, datatype=field.datatype, current_value=first_attr(col, "value")))
            if field.is_calculated and field.formula:
                calculations.append(TableauCalculation(
                    name=field.name,
                    datasource=ds_name_clean,
                    formula=field.formula,
                    return_type=field.datatype,
                    dependencies=sorted(set(FIELD_REF_RE.findall(field.formula))),
                ))
        for filt in [f for f in ds.iter() if tag_name(f) in {"filter", "extract-filter"}]:
            tds.filters.append(dict(filt.attrib) | ({"text": text_of(filt)} if text_of(filt) else {}))
        datasources.append(tds)

    worksheets: list[TableauWorksheet] = []
    for ws in iter_by_tag(root, "worksheet"):
        name = first_attr(ws, "name", default="Worksheet") or "Worksheet"
        rows: list[str] = []
        cols: list[str] = []
        filters: list[str] = []
        fields: set[str] = set()
        marks_type = None
        encodings: dict[str, Any] = {}
        for elem in ws.iter():
            t = tag_name(elem)
            if t == "rows" and text_of(elem):
                rows.extend(FIELD_REF_RE.findall(text_of(elem)) or [text_of(elem)])
            elif t == "cols" and text_of(elem):
                cols.extend(FIELD_REF_RE.findall(text_of(elem)) or [text_of(elem)])
            elif t == "filter":
                ref = first_attr(elem, "column", "field", default=text_of(elem))
                if ref:
                    filters.append(ref)
                    fields.update(FIELD_REF_RE.findall(ref))
            elif t == "mark":
                marks_type = first_attr(elem, "class", "type")
            elif t in {"color", "size", "label", "tooltip", "detail", "path", "shape"}:
                encodings[t] = dict(elem.attrib) | ({"text": text_of(elem)} if text_of(elem) else {})
                fields.update(FIELD_REF_RE.findall(str(encodings[t])))
            else:
                fields.update(FIELD_REF_RE.findall(str(elem.attrib)))
        fields.update(rows)
        fields.update(cols)
        worksheets.append(TableauWorksheet(
            name=name,
            rows=sorted(set(rows)),
            columns=sorted(set(cols)),
            marks_type=marks_type,
            filters=filters,
            encodings=encodings,
            fields_used=sorted({clean_name(f) for f in fields if f}),
        ))

    dashboards: list[TableauDashboard] = []
    for db in iter_by_tag(root, "dashboard"):
        name = first_attr(db, "name", default="Dashboard") or "Dashboard"
        zones = [z for z in db.iter() if tag_name(z) == "zone"]
        worksheets_in_dash: list[str] = []
        objects = []
        for z in zones:
            z_name = first_attr(z, "name")
            z_type = first_attr(z, "type")
            if z_name:
                worksheets_in_dash.append(z_name)
            objects.append(dict(z.attrib))
        dashboards.append(TableauDashboard(name=name, worksheets=sorted(set(worksheets_in_dash)), objects=objects))

    stories: list[TableauStory] = []
    for st in iter_by_tag(root, "story"):
        name = first_attr(st, "name", default="Story") or "Story"
        sheets = []
        for elem in st.iter():
            val = first_attr(elem, "worksheet", "dashboard", "name")
            if val:
                sheets.append(val)
        stories.append(TableauStory(name=name, sheets=sorted(set(sheets))))

    # Link calc usages by worksheet field reference.
    for calc in calculations:
        used = [w.name for w in worksheets if clean_name(calc.name) in {clean_name(f) for f in w.fields_used}]
        calc.used_in = used
    for ds in datasources:
        for f in ds.fields:
            f.used_in = [w.name for w in worksheets if clean_name(f.name) in {clean_name(x) for x in w.fields_used}]
    # Infer missing physical base columns from calc dependencies
    for ds in datasources:
        existing_fields = {clean_name(f.name).casefold() for f in ds.fields}
        implicit_fields = set()
        
        for calc in calculations:
            if clean_name(calc.datasource or "") == clean_name(ds.name):
                for dep in calc.dependencies:
                    clean_dep = clean_name(dep)
                    if clean_dep.casefold() not in existing_fields:
                        implicit_fields.add(dep)
        
        # Also include fields used in worksheets if they look like field references
        for ws in worksheets:
            for f in ws.fields_used:
                clean_f = clean_name(f)
                if clean_f and clean_f.casefold() not in existing_fields:
                    # Ignore internal Tableau fields (Measure Names, etc.)
                    if not is_tableau_generated_field(clean_f):
                        implicit_fields.add(f)
                        existing_fields.add(clean_f.casefold())
                        
        for field_name in implicit_fields:
            if is_tableau_generated_field(field_name):
                continue
            ds.fields.append(TableauField(
                id=_id(ds.name, field_name),
                datasource=ds.name,
                name=field_name,
                caption=field_name,
                datatype="Text", # Fallback type for implicit fields
                role="dimension",
                is_calculated=False,
                is_parameter=False,
                expression=None
            ))

    return {
        "workbook_name": workbook_name,
        "version": version,
        "datasources": datasources,
        "worksheets": worksheets,
        "dashboards": dashboards,
        "stories": stories,
        "parameters": parameters,
        "calculations": calculations,
    }
