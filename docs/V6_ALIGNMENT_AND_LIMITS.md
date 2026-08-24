# V7 Alignment to Tableau-to-Power BI Migration Rules

## Core principle

V7 follows the rule: **migrate business logic, not Tableau mechanics**.

The application does not claim blind perfect automation. It classifies every extracted item into one of these targets:

- Source SQL / native query review
- Power Query M transformation
- Power BI semantic model relationship
- DAX measure
- DAX calculated column
- Visual/rebuild plan
- Manual review
- Omit from Power BI model

## Tableau combination logic handling

| Tableau object | V7 target | Notes |
|---|---|---|
| Relationship | Power BI model relationship | Not converted to Power Query Merge by default |
| Physical join | Power Query Merge / source SQL only where physical output is required | Row-count and grain validation required |
| Union | Power Query Append | Same-structure tables only |
| Blend / federated behavior | Semantic model, bridge table, composite model, or manual review | Tableau primary/secondary blend mechanics are not copied |
| Custom SQL / RAWSQL | Value.NativeQuery / SQL view placeholder | Security and folding review required |

## Preparation logic handling

| Tableau preparation logic | V7 target |
|---|---|
| Rename field | Power Query/model display name |
| Hide field | Semantic metadata / omit if unused |
| Change datatype | Power Query type step + semantic metadata |
| Split column | Power Query review plan |
| Pivot/unpivot | Power Query review plan |
| Extract/data source filters | Power Query/source/DAX/RLS review |
| Parameters | Disconnected table / what-if / field parameter / SELECTEDVALUE |
| Sets/groups/bins | DAX/M/manual review |
| Aliases | Mapping table / replace values / display metadata |

## Omit rules

V7 explicitly avoids migrating these blindly:

- Tableau relationship auto-join behavior
- Unnecessary physical joins when Tableau used logical relationships
- Tableau blending mechanics
- Tableau extract storage choices as-is
- Tableau context filters as a literal feature
- Generated Measure Names/Measure Values fields unless business-used
- Visual-only formatting as data model transformations
- Tableau table calculations as static Power Query columns
- Pre-aggregated/report total rows as facts without validation

## Accuracy and validation

V7 exports `validation/reconciliation_plan.json` with checkpoints for:

1. Source row counts
2. Transformation grain
3. Relationship behavior
4. Measures and LOD results
5. Visual behavior
6. PBIP safe-mode openability

This is required because Tableau's worksheet query layer, relationships, order of operations, table calculations, and LOD behavior can be context-specific.


## V7 TDE rule

Legacy `.tde` extracts are treated as output artifacts/materialized snapshots. The app does not design the target as `Tableau TDE -> Power BI`; it recommends recovering original source systems and transformation logic, rebuilding through Power Query/Dataflow/Fabric/SQL staging, and validating against the TDE baseline.
