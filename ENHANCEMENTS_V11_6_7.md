# TABLEAU2PBI v11.6.7 — XML Power Query Handling

## Fixed

1. **Business XML sources inside Tableau packages** are now handled as true XML data sources when Tableau metadata references them.
2. Power Query XML generation no longer stops at the nested `Xml.Tables(...)` navigation result.
3. Generated M recursively expands nested **table** and **record** columns (up to a safe depth limit).
4. Unique leaf column names are normalized (for example `root.orders.order.Region` can resolve to `Region` when unambiguous).
5. XML output is aligned to the expected Tableau/semantic schema before datatype enforcement.
6. `MissingField.UseNull` is used for schema-safe XML alignment so a missing optional XML element does not break PBIP loading.
7. Case-only XML column differences are normalized to the semantic model names.
8. XML preview/profiling now detects repeating business row elements when a wrapper/root causes `pandas.read_xml()` to return only a navigation/wrapper column.
9. XML attributes and simple child/grandchild values are included in preview profiling.
10. Tableau workbook/data-source XML, manifests, metadata, lineage, config, validation, and other sidecar XML remain inventory/recovery artifacts and are not promoted as business semantic tables unless Tableau explicitly references them as a source.

## Regression tests

- `xml_powerquery_regression_test.py` — PASS
- `semantic_cleanup_regression_test.py` — PASS
- `schema_alignment_regression_test.py` — PASS
- `path_regression_test.py` — PASS

## Design rule

**Tableau XML definition/metadata != XML business data source.**

- Tableau XML definition files are parsed by the Tableau compiler/inventory pipeline.
- XML business data files are translated to Power Query using `Xml.Tables`, recursive expansion, schema normalization, datatype enforcement, and semantic-model alignment.
