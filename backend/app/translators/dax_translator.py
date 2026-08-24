from __future__ import annotations
import re
from app.core.name_sanitizer import clean_name, dax_column, dax_table
from app.models.schemas import TableauCalculation

FIELD_REF_RE = re.compile(r"\[([^\]]+)\]")

UNSUPPORTED_PATTERNS = {
    "SCRIPT_": "External Tableau script functions require manual review.",
    "MODEL_EXTENSION_": "Tableau model extension functions require manual review.",
    "RAWSQL_": "RAWSQL should remain source/native SQL and requires security review.",
    "PREVIOUS_VALUE": "Tableau table calculation addressing/partitioning requires manual review.",
    "LOOKUP": "Tableau table calculation addressing/partitioning requires manual review.",
    "WINDOW_": "Window table calculations require DAX context review.",
    "INDEX()": "Index table calculations require visual context review.",
    "SIZE()": "Size table calculation requires visual context review.",
}

AGGREGATES = {
    "SUM": "SUM",
    "AVG": "AVERAGE",
    "AVERAGE": "AVERAGE",
    "COUNT": "COUNT",
    "COUNTD": "DISTINCTCOUNT",
    "MIN": "MIN",
    "MAX": "MAX",
    "MEDIAN": "MEDIAN",
    "STDEV": "STDEV.S",
    "STDEVP": "STDEV.P",
    "VAR": "VAR.S",
    "VARP": "VAR.P",
}

TEXT_FUNCTIONS = {
    "CONTAINS": "CONTAINSSTRING",
    "STARTSWITH": "STARTSWITH",
    "ENDSWITH": "ENDSWITH",
    "LEN": "LEN",
    "LEFT": "LEFT",
    "RIGHT": "RIGHT",
    "MID": "MID",
    "LOWER": "LOWER",
    "UPPER": "UPPER",
    "TRIM": "TRIM",
    "REPLACE": "SUBSTITUTE",
}


def _replace_fields(expr: str, table: str) -> str:
    return FIELD_REF_RE.sub(lambda m: dax_column(table, m.group(1)), expr)


def _translate_date_and_functions(expr: str) -> str:
    # DATEPART('year', ...) -> YEAR(...)
    expr = re.sub(r"(?is)\bDATEPART\s*\(\s*['\"]year['\"]\s*,\s*(.+?)\s*\)", r"YEAR(\1)", expr)
    expr = re.sub(r"(?is)\bDATEPART\s*\(\s*['\"]month['\"]\s*,\s*(.+?)\s*\)", r"MONTH(\1)", expr)
    expr = re.sub(r"(?is)\bDATEPART\s*\(\s*['\"]quarter['\"]\s*,\s*(.+?)\s*\)", r"QUARTER(\1)", expr)
    expr = re.sub(r"(?is)\bDATEPART\s*\(\s*['\"]day['\"]\s*,\s*(.+?)\s*\)", r"DAY(\1)", expr)
    
    # DATENAME('month', ...) -> FORMAT(..., "mmmm")
    expr = re.sub(r"(?is)\bDATENAME\s*\(\s*['\"]month['\"]\s*,\s*(.+?)\s*\)", r'FORMAT(\1, "mmmm")', expr)
    expr = re.sub(r"(?is)\bDATENAME\s*\(\s*['\"]weekday['\"]\s*,\s*(.+?)\s*\)", r'FORMAT(\1, "dddd")', expr)
    
    # STR(DATEPART('quarter', x)) -> QUARTER(x) or STR(x) -> FORMAT(x, "@")
    expr = re.sub(r"(?is)\bSTR\s*\(\s*QUARTER\s*\((.+?)\)\s*\)", r"QUARTER(\1)", expr)
    expr = re.sub(r"(?is)\bSTR\s*\(\s*(.+?)\s*\)", r"\1", expr)
    
    # String concatenation with + -> &
    expr = re.sub(r'(["\'][^"\']*["\'])\s*\+\s*', r'\1 & ', expr)
    expr = re.sub(r'\s*\+\s*(["\'][^"\']*["\'])', r' & \1', expr)
    return expr


def _translate_if(expr: str, table: str) -> str | None:
    expr_clean = expr.strip()
    if not re.match(r"(?is)^IF\s+", expr_clean) or not re.search(r"(?is)\bEND$", expr_clean):
        return None
        
    body = re.sub(r"(?is)^IF\s+", "", expr_clean)
    body = re.sub(r"(?is)\s+END$", "", body)
    
    parts = re.split(r"(?is)\bELSEIF\b", body)
    
    last_part = parts[-1]
    else_expr = "BLANK()"
    if re.search(r"(?is)\bELSE\b", last_part):
        subparts = re.split(r"(?is)\bELSE\b", last_part, maxsplit=1)
        parts[-1] = subparts[0]
        else_expr = subparts[1].strip()
        
    branches = []
    for p in parts:
        if re.search(r"(?is)\bTHEN\b", p):
            cond, res = re.split(r"(?is)\bTHEN\b", p, maxsplit=1)
            branches.append((cond.strip(), res.strip()))
        else:
            return None
            
    cur = _translate_date_and_functions(_replace_fields(else_expr, table))
    for cond, res in reversed(branches):
        cond_dax = _translate_date_and_functions(_replace_fields(cond, table))
        res_dax = _translate_date_and_functions(_replace_fields(res, table))
        cur = f"IF({cond_dax}, {res_dax}, {cur})"
    return cur


def _translate_case(expr: str, table: str) -> str | None:
    if not re.match(r"(?is)^\s*CASE\s+", expr):
        return None
    # Conservative conversion: manual-friendly SWITCH(TRUE()) skeleton.
    cleaned = _replace_fields(expr, table)
    return "/* Review CASE conversion */ SWITCH(TRUE(), " + cleaned.replace("CASE", "").replace("WHEN", "/*WHEN*/").replace("THEN", ",").replace("ELSE", ", /*ELSE*/").replace("END", "") + ")"


def _translate_lod(expr: str, table: str) -> str | None:
    m = re.match(r"(?is)^\s*\{\s*FIXED\s+(.+?)\s*:\s*(.+?)\s*\}\s*$", expr)
    if not m:
        return None
    dims = FIELD_REF_RE.findall(m.group(1))
    agg_expr = translate_formula_to_dax(m.group(2), table, as_measure=True)[0]
    if dims:
        dim_refs = ", ".join(dax_column(table, d) for d in dims)
        return f"CALCULATE({agg_expr}, ALLEXCEPT(__TABLE__({dax_table(table)}), {dim_refs}))"
    return f"CALCULATE({agg_expr}, REMOVEFILTERS(__TABLE__({dax_table(table)})))"


def translate_formula_to_dax(formula: str, table: str, as_measure: bool = False) -> tuple[str, float, list[str]]:
    warnings: list[str] = []
    original = (formula or "").strip()
    upper = original.upper()
    for pattern, warning in UNSUPPORTED_PATTERNS.items():
        if pattern in upper:
            warnings.append(warning)
    lod = _translate_lod(original, table)
    if lod:
        return lod, 0.78, warnings + ["LOD conversion requires context validation against Tableau result."]
    if_expr = _translate_if(original, table)
    if if_expr:
        return if_expr, 0.82, warnings
    case_expr = _translate_case(original, table)
    if case_expr:
        return case_expr, 0.55, warnings + ["CASE was converted to a review skeleton; validate all branches."]

    for source, target in AGGREGATES.items():
        m = re.match(rf"(?is)^\s*{source}\s*\(\s*\[([^\]]+)\]\s*\)\s*$", original)
        if m:
            return f"{target}({dax_column(table, m.group(1))})", 0.95, warnings

    expr = original
    expr = _translate_date_and_functions(expr)
    expr = re.sub(r"(?i)IFNULL\((.+?),(.+?)\)", r"COALESCE(\1,\2)", expr)
    expr = re.sub(r"(?i)ZN\((.+?)\)", r"COALESCE(\1, 0)", expr)
    expr = re.sub(r"(?i)ISNULL\((.+?)\)", r"ISBLANK(\1)", expr)
    expr = re.sub(r"(?i)COUNTD\(", "DISTINCTCOUNT(", expr)
    expr = re.sub(r"(?i)AVG\(", "AVERAGE(", expr)
    for s, t in TEXT_FUNCTIONS.items():
        expr = re.sub(rf"(?i)\b{s}\s*\(", f"{t}(", expr)
    expr = _replace_fields(expr, table)
    confidence = 0.68 if warnings else 0.74
    if re.search(r"\bTHEN\b|\bEND\b|\bFIXED\b|\bINCLUDE\b|\bEXCLUDE\b", upper):
        warnings.append("Formula contains Tableau context syntax that was not fully converted.")
        confidence = min(confidence, 0.45)
    return expr, confidence, warnings


def classify_and_translate(calc: TableauCalculation, default_table: str) -> TableauCalculation:
    formula = calc.formula or ""
    upper = formula.upper()
    has_agg = bool(re.search(r"\b(SUM|AVG|AVERAGE|COUNT|COUNTD|MIN|MAX|MEDIAN|STDEV|VAR|PERCENTILE)\s*\(", upper))
    has_lod = any(x in upper for x in ["{FIXED", "{ INCLUDE", "{EXCLUDE", "FIXED ", "INCLUDE ", "EXCLUDE "])
    has_table_calc = any(x in upper for x in ["WINDOW_", "LOOKUP", "RUNNING_", "RANK", "INDEX", "FIRST()", "LAST()", "PREVIOUS_VALUE"])
    if has_agg or has_lod or has_table_calc:
        calc.classification = "Aggregation / semantic calculation"
        calc.target_object_type = "measure" if not has_table_calc else "measure_manual_review"
    else:
        calc.classification = "Row-level deterministic calculation"
        calc.target_object_type = "calculated_column"
    dax, conf, warnings = translate_formula_to_dax(formula, default_table, as_measure=calc.target_object_type.startswith("measure"))
    calc.generated_expression = dax
    calc.confidence_score = conf
    calc.warnings = list(dict.fromkeys(calc.warnings + warnings))
    if conf < 0.7:
        calc.manual_review_notes.append("Validate generated DAX against Tableau output before business sign-off.")
    return calc
