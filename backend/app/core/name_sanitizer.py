from __future__ import annotations
import re

_RESERVED = {"table", "column", "measure", "relationship", "source", "null", "true", "false"}


def clean_name(value: str | None, fallback: str = "Object") -> str:
    raw = (value or fallback).strip().strip("[]'$")
    raw = re.sub(r"[^A-Za-z0-9_ ]+", "_", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        raw = fallback
    if raw.lower() in _RESERVED:
        raw = f"{raw}_Object"
    if raw[0].isdigit():
        raw = f"_{raw}"
    return raw


def dax_table(value: str) -> str:
    return "'" + clean_name(value).replace("'", "''") + "'"


def dax_column(table: str, column: str) -> str:
    return f"{dax_table(table)}[{clean_name(column)}]"
