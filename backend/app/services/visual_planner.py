from __future__ import annotations
from app.models.schemas import TableauWorksheet


def recommend_visual(worksheet: TableauWorksheet) -> dict:
    marks = (worksheet.marks_type or "").lower()
    rows = worksheet.rows
    cols = worksheet.columns
    recommendation = "Table / Matrix"
    notes: list[str] = []
    if "bar" in marks:
        recommendation = "Clustered Bar/Column Chart"
    elif "line" in marks:
        recommendation = "Line Chart"
    elif "area" in marks:
        recommendation = "Area Chart"
    elif "pie" in marks:
        recommendation = "Pie/Donut Chart"
    elif "map" in marks or any("lat" in f.lower() or "lon" in f.lower() or "latitude" in f.lower() for f in rows + cols):
        recommendation = "Map / Azure Maps"
    elif "circle" in marks or "scatter" in marks:
        recommendation = "Scatter Chart"
    elif len(rows) >= 1 and len(cols) >= 1:
        recommendation = "Matrix or Chart depending on measure usage"
    if worksheet.encodings.get("path"):
        notes.append("Path encoding may require custom visual or manual build.")
    if "dual" in str(worksheet.encodings).lower():
        notes.append("Dual axis charts should be reviewed; Power BI combo chart may be suitable.")
    return {
        "worksheet": worksheet.name,
        "target_powerbi_page": worksheet.name,
        "recommended_visual": recommendation,
        "rows": rows,
        "columns": cols,
        "marks_type": worksheet.marks_type,
        "filters": worksheet.filters,
        "encodings": worksheet.encodings,
        "manual_build_notes": notes,
        "safe_mode_visual_json": False,
    }


def build_visual_plan(worksheets: list[TableauWorksheet]) -> list[dict]:
    return [recommend_visual(w) for w in worksheets]
