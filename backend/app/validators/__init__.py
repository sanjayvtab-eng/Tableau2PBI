"""Validator package bootstrap.

Safe Openable Mode must never write invalid DAX into a PBIP, but an unsupported
Tableau calculation should also not make the entire otherwise-valid export fail.

The core PBIP validator intentionally reports unsafe FIXED LOD/ALLEXCEPT cases as
blockers.  This package wrapper converts only those calculation-specific blockers
into safe omissions: the offending measure is removed from model.bim, the model is
validated again, and a warning check is retained for the migration report/export
validation artifact.

All structural/model/source blockers continue to fail export normally.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import pbip_integrity as _pbip_integrity

_original_validate_pbip_tree = _pbip_integrity.validate_pbip_tree

_LOD_BLOCKER_PATTERNS = (
    re.compile(r"^FIXED LOD measure ([^\[]+)\[([^\]]+)\] cannot be mapped safely:"),
    re.compile(r"^FIXED LOD measure ([^\[]+)\[([^\]]+)\] could not resolve final physical column names"),
    re.compile(r"^Invalid ALLEXCEPT table scope in ([^\[]+)\[([^\]]+)\]:"),
)


def _unsafe_measure_keys(blockers: list[str]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for blocker in blockers:
        text = str(blocker or "").strip()
        for pattern in _LOD_BLOCKER_PATTERNS:
            match = pattern.match(text)
            if match:
                result.add((match.group(1).strip().casefold(), match.group(2).strip().casefold()))
                break
    return result


def _remove_unsafe_lod_measures(pbip_root: Path, keys: set[tuple[str, str]]) -> list[str]:
    model_files = list(pbip_root.glob("*.SemanticModel/model.bim"))
    if len(model_files) != 1 or not keys:
        return []

    model_file = model_files[0]
    try:
        doc = json.loads(model_file.read_text(encoding="utf-8-sig"))
    except Exception:
        return []

    removed: list[str] = []
    for table in (doc.get("model") or {}).get("tables", []) or []:
        table_name = str(table.get("name") or "")
        kept = []
        for measure in table.get("measures", []) or []:
            measure_name = str(measure.get("name") or "")
            if (table_name.casefold(), measure_name.casefold()) in keys:
                removed.append(f"{table_name}[{measure_name}]")
                continue
            kept.append(measure)
        table["measures"] = kept

    if removed:
        model_file.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return removed


def validate_pbip_tree(pbip_root: Path):
    checks, blockers = _original_validate_pbip_tree(pbip_root)

    unsafe_keys = _unsafe_measure_keys(blockers)
    if not unsafe_keys:
        return checks, blockers

    removed = _remove_unsafe_lod_measures(pbip_root, unsafe_keys)
    if not removed:
        return checks, blockers

    # Re-run the authoritative validator after removing only unsupported LOD measures.
    # Any unrelated structural/source/model failure must still block export.
    second_checks, second_blockers = _original_validate_pbip_tree(pbip_root)

    warning_checks = [
        {
            "check": "Safe Openable Mode - unsupported FIXED LOD",
            "status": "Warning",
            "message": (
                f"{label} was omitted from the executable semantic model because its Tableau FIXED LOD "
                "requires relationship-aware/manual DAX. The rest of the PBIP remains exportable."
            ),
        }
        for label in removed
    ]

    # Preserve useful first-pass diagnostics without carrying the calculation-specific
    # blockers that have now been safely removed from the model.
    retained_first_checks = [
        c for c in checks
        if c.get("check") not in {"DAX FIXED LOD repair"}
    ]
    return retained_first_checks + warning_checks + second_checks, second_blockers


# Patch the submodule attribute during package initialization. Existing imports such as
# `from app.validators.pbip_integrity import validate_pbip_tree` receive this wrapper.
_pbip_integrity.validate_pbip_tree = validate_pbip_tree

__all__ = ["validate_pbip_tree"]
