from __future__ import annotations
import itertools, re
from collections import defaultdict
from app.core.name_sanitizer import clean_name
from app.models.schemas import MigrationProject, RelationshipCandidate

MIN_FINAL_SCORE = 0.82


def _norm(value: str) -> str:
    return clean_name(value or "").lower().replace(" ", "_")


def _family(table: str) -> str:
    n = _norm(table)
    return re.sub(r'[_-]?(19|20)\d{2}$', '', n)


def _dimension_affinity(table: str, column: str) -> bool:
    t = _family(table).rstrip('s')
    c = _norm(column)
    c = re.sub(r'(_?id|_?key|_?code|_?number)$', '', c).rstrip('s')
    if not t or not c:
        return False
    # customers -> Customer ID, products -> Product ID, regions -> Region Code, etc.
    return t == c or t.endswith('_' + c) or c.endswith('_' + t)


def _choose_sides(left, right, lc: dict, rc: dict):
    lname, rname = str(lc.get('name','')), str(rc.get('name',''))
    # Never infer relationships between sibling partition/append tables such as
    # orders_2025 and orders_2026. Those are transformation candidates, not model edges.
    if _family(left.name) == _family(right.name):
        return None
    la, ra = _dimension_affinity(left.name, lname), _dimension_affinity(right.name, rname)
    lp, rp = bool(lc.get('possible_key')), bool(rc.get('possible_key'))
    if ra and not la and rc.get('source_scope') == 'source_preview' and lc.get('source_scope') == 'source_preview':
        return left, lc, right, rc, 'dimension-table key affinity with source profile'
    if la and not ra and lc.get('source_scope') == 'source_preview' and rc.get('source_scope') == 'source_preview':
        return right, rc, left, lc, 'dimension-table key affinity with source profile'
    # Uniqueness by itself is not sufficient for automatic model creation because
    # a sampled fact column can also appear unique. If table/key semantics do not
    # identify a clear dimension side, keep it out of the final relationship model.
    return None


def _would_create_cycle(graph: dict[str, set[str]], a: str, b: str) -> bool:
    stack, seen = [a], set()
    while stack:
        n = stack.pop()
        if n == b:
            return True
        if n in seen:
            continue
        seen.add(n); stack.extend(graph.get(n, set()))
    return False


def infer_relationships(project: MigrationProject) -> list[RelationshipCandidate]:
    tables = [t for t in project.semantic_tables if t.include_in_export]
    proposed: list[RelationshipCandidate] = []
    for left, right in itertools.combinations(tables, 2):
        candidates: list[RelationshipCandidate] = []
        for lc in left.columns:
            if lc.get('calculated'):
                continue
            for rc in right.columns:
                if rc.get('calculated'):
                    continue
                ln, rn = _norm(str(lc.get('name',''))), _norm(str(rc.get('name','')))
                # Final-model inference requires the same business key name. Similar-name
                # guesses are intentionally kept out of the normal relationship screen.
                if not ln or ln != rn:
                    continue
                sides = _choose_sides(left, right, lc, rc)
                if not sides:
                    continue
                ft, fc, tt, tc, evidence = sides
                score = 0.74
                if evidence.startswith('dimension-table key affinity'): score += 0.14
                if bool(tc.get('possible_key')): score += 0.08
                if fc.get('data_type') and fc.get('data_type') == tc.get('data_type'): score += 0.04
                score = min(score, 0.98)
                if score < MIN_FINAL_SCORE:
                    continue
                candidates.append(RelationshipCandidate(
                    id='pending', from_table=ft.name, from_column=clean_name(fc.get('name')),
                    to_table=tt.name, to_column=clean_name(tc.get('name')),
                    cardinality='Many-to-one', cross_filter_direction='Single', active=True,
                    confidence_score=round(score,2), reason=f'Final relationship inferred from exact key-name match and {evidence}.',
                    manual_review=False,
                ))
        if candidates:
            candidates.sort(key=lambda r:r.confidence_score, reverse=True)
            proposed.append(candidates[0])

    graph: dict[str,set[str]] = defaultdict(set)
    final: list[RelationshipCandidate] = []
    seen_pairs=set()
    for r in sorted(proposed,key=lambda x:x.confidence_score, reverse=True):
        pair=tuple(sorted((r.from_table.lower(),r.to_table.lower())))
        if pair in seen_pairs:
            continue
        if _would_create_cycle(graph,r.from_table,r.to_table):
            continue
        seen_pairs.add(pair); graph[r.from_table].add(r.to_table); graph[r.to_table].add(r.from_table); final.append(r)
    for i,r in enumerate(final,1): r.id=f'rel_{i}'
    return final
