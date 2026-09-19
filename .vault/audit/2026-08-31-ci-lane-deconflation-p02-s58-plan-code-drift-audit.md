---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3b15b25673fea63a1493ada88b70d752712b4923daed54eb0159b11771c43e40'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` audit: `P02.S58 plan-to-code drift`

## Scope

- Checked plan claim `P02.S58` in `2026-08-05-ci-lane-deconflation-plan`.
- Its named gate, `src/cadrumo/application/calculations/tests/test_grouping_dispatch_coverage.py`, and its immutable Git history.
- Existing ci-lane audits were scanned for `P02.S58`, the claimed mesh category, and the two grouping values; no overlapping curation finding was found.

## Findings

### checked-plan-claim-diverges-from-code-history | high | P02.S58 is marked done but its claimed gate change is absent

The checked S58 row was introduced by plan-only commit `bc1913fdf0b97d34ed5941da5fec26263bd54931`. It claims that the named gate added `_MESH_RESOLVED_GROUPINGS` to distinguish the mesh-resolved `per_inventory_activity` path from invoice handling and correctly account for `contraparte_clave`. The current gate contains only `_INVOICE_GROUPINGS` and no mesh-resolved category. Its complete followed history begins with creation in `85f3f3295923347f42d8052c5f6ee29b23ea1a83` and has only later import/relocation changes. Exact history searches for `_MESH_RESOLVED_GROUPINGS`, `per_inventory_activity`, and `contraparte_clave` in that gate return no introducing or removing commit. There is also no S58 execution record. This prevents an honest reconstruction of implementation or test evidence.

## Recommendations

- Restore the verified gate implementation and record fresh evidence, or uncheck S58 and replan it. The choice requires owner judgment; this audit does not select either remediation.
- Do not create an S58 execution record until a committed implementation and literal verification evidence exist.
