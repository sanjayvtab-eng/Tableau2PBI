from __future__ import annotations
import json
import warnings
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
import pandas as pd
from app.models.schemas import DataPreview, DataProfileColumn, SourceMapping

TYPE_MAP = {
    "integer": "Whole Number",
    "floating": "Decimal Number",
    "boolean": "True/False",
    "datetime": "DateTime",
    "date": "Date",
    "string": "Text",
}


def _norm(value: str) -> str:
    return value.replace("\\", "/").lower().strip("/")


def _candidate_paths(mapping: SourceMapping, workspace_path: Path) -> list[Path]:
    workspace_path = workspace_path.resolve()
    values = [mapping.target_file_path, mapping.detected_source_path]
    candidates: list[Path] = []
    for value in values:
        if not value:
            continue
        text = str(value).strip().strip('"')
        p = Path(text)
        if p.is_absolute():
            candidates.append(p)
        candidates.append((workspace_path / text).resolve())
        candidates.append((workspace_path / "uploads" / Path(text).name).resolve())
        candidates.append((workspace_path / "extracted" / text).resolve())
        # Match by exact relative suffix and by basename under workspace.
        tail = _norm(text)
        name = Path(text).name.lower()
        for f in workspace_path.rglob("*"):
            if not f.is_file():
                continue
            rel = _norm(str(f.relative_to(workspace_path)))
            if rel.endswith(tail) or f.name.lower() == name:
                candidates.append(f.resolve())
    # unique existing first, but keep non-existing for error context.
    seen: set[str] = set()
    unique: list[Path] = []
    for p in candidates:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _read_sample(path: Path, connector: str) -> pd.DataFrame:
    ext = path.suffix.lower()
    if connector in {"CSV", "Text"} or ext in {".csv", ".txt", ".tsv"}:
        sep = "\t" if ext == ".tsv" else None
        return pd.read_csv(path, sep=sep, engine="python", nrows=500)
    if connector == "Excel" or ext in {".xlsx", ".xls"}:
        return pd.read_excel(path, nrows=500)
    if connector == "JSON" or ext == ".json":
        df = pd.read_json(path)
        if isinstance(df, pd.Series):
            return df.to_frame()
        return df.head(500)
    if connector == "XML" or ext == ".xml":
        try:
            # pandas.read_xml works for many regular rowsets.
            df = pd.read_xml(path)
            useful_values = int(df.notna().sum().sum()) if isinstance(df, pd.DataFrame) else 0
            if isinstance(df, pd.DataFrame) and len(df.columns) > 0 and useful_values > 0 and (len(df.columns) > 1 or len(df) > 1):
                return df.head(500)
        except Exception:
            pass
        try:
            # Tableau XML data sources can contain wrapper/root elements around the
            # repeating business row node. Detect the most useful repeating element and
            # flatten attributes + leaf descendants into a tabular preview.
            root = ET.parse(path).getroot()
            def local(tag: str) -> str:
                return str(tag).split('}', 1)[-1]
            elems = list(root.iter())
            counts = Counter(local(e.tag) for e in elems)
            candidates = []
            for tag, count in counts.items():
                if count < 2:
                    continue
                tagged = [e for e in elems if local(e.tag) == tag]
                leaf_score = max((sum(1 for c in list(e) if len(list(c)) == 0) for e in tagged[:20]), default=0)
                attr_score = max((len(e.attrib) for e in tagged[:20]), default=0)
                if leaf_score + attr_score > 0:
                    candidates.append((count, leaf_score + attr_score, tag, tagged))
            if candidates:
                _, _, _, rows_elems = max(candidates, key=lambda x: (x[0] * max(x[1], 1), x[0]))
                rows = []
                for e in rows_elems[:500]:
                    row = {local(k): v for k, v in e.attrib.items()}
                    for c in list(e):
                        key = local(c.tag)
                        if len(list(c)) == 0:
                            row[key] = (c.text or '').strip() or None
                        else:
                            # Preserve simple grandchildren using leaf names.
                            for gc in list(c):
                                if len(list(gc)) == 0:
                                    gk = local(gc.tag)
                                    if gk in row:
                                        gk = f"{key}.{gk}"
                                    row[gk] = (gc.text or '').strip() or None
                    if row:
                        rows.append(row)
                if rows:
                    return pd.DataFrame(rows).head(500)
        except Exception:
            pass
        # XML was readable as text but not safely tabular. Keep it review-only in preview;
        # source mapping/model rules still decide whether it is a real business source.
        return pd.DataFrame([{"xml_file": path.name, "preview_text": path.read_text(encoding="utf-8", errors="ignore")[:1000]}])
    if connector == "Parquet" or ext == ".parquet":
        return pd.read_parquet(path).head(500)
    raise ValueError(f"Preview not implemented for connector {connector}")


def _profile_column(series: pd.Series) -> DataProfileColumn:
    non_null = series.dropna()
    total = len(series)
    null_count = int(series.isna().sum())
    distinct = int(non_null.nunique(dropna=True)) if total else 0
    numeric = pd.to_numeric(non_null, errors="coerce") if total else pd.Series([], dtype="float64")
    numeric_conf = float(numeric.notna().mean()) if len(non_null) else 0.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dt = pd.to_datetime(non_null, errors="coerce", utc=False) if len(non_null) else pd.Series([], dtype="datetime64[ns]")
    date_conf = float(dt.notna().mean()) if len(non_null) else 0.0
    text_conf = 1.0 - max(numeric_conf, date_conf)
    detected = "Text"
    if str(series.dtype).lower() == "bool":
        detected = "True/False"
    elif numeric_conf >= 0.95:
        detected = "Whole Number" if len(numeric.dropna()) and (numeric.dropna() % 1 == 0).all() else "Decimal Number"
    elif date_conf >= 0.9:
        detected = "DateTime"
    possible_key = distinct == len(non_null) and len(non_null) > 0 and null_count == 0
    role = "measure" if detected in {"Whole Number", "Decimal Number", "Fixed Decimal / Currency"} and not possible_key else "dimension"
    col_warnings = []
    if total and null_count / total > 0.5:
        col_warnings.append("High null ratio; validate datatype and relationship usage.")
    return DataProfileColumn(
        column_name=str(series.name),
        detected_type=detected,
        null_count=null_count,
        distinct_count_estimate=distinct,
        numeric_confidence=round(numeric_conf, 3),
        date_confidence=round(date_conf, 3),
        text_confidence=round(max(text_conf, 0), 3),
        possible_key=possible_key,
        dimension_or_measure=role,
        warnings=col_warnings,
    )


def preview_mapping(mapping: SourceMapping, workspace_path: Path) -> DataPreview:
    warnings_list: list[str] = []
    candidates = _candidate_paths(mapping, workspace_path)
    tried: list[str] = []
    for path in candidates:
        tried.append(str(path))
        if path.exists() and path.is_file():
            try:
                df = _read_sample(path, mapping.target_connector)
                rows = json.loads(df.head(10).to_json(orient="records", date_format="iso"))
                cols = [_profile_column(df[c]) for c in df.columns]
                return DataPreview(source_id=mapping.source_id, available=True, rows=rows, columns=cols, warnings=[])
            except Exception as exc:
                warnings_list.append(f"Could not preview {path.name}: {exc}")
    warnings_list.append("No local readable source found. Datatypes will be inferred from Tableau metadata and can be overridden manually.")
    if tried:
        warnings_list.append("Path search tried: " + "; ".join(tried[:5]) + ("; ..." if len(tried) > 5 else ""))
    return DataPreview(source_id=mapping.source_id, available=False, rows=[], columns=[], warnings=warnings_list)
