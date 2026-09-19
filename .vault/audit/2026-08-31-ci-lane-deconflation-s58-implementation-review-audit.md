---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:73bb79f3f71fecc69292709773851a15978052cd830296224e13bf77865c3fe3'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` audit: `P02.S58 implementation review`

## Scope

Independent review of immutable P02.S58 implementation commit `e99f1c3e7c`, its execution record, the restored grouping-dispatch gate, and the public inventory calculation-route ownership it proves.

## Findings

No HIGH or CRITICAL findings. The gate now classifies `contraparte_clave` with the invoice-row groupings and records `per_inventory_activity` against `BindingSourceKind.INVENTORY`, rather than using a bare allowlist. Its route proof separately requires exactly one `InventorySourceResolver` owner at the `mesh` stage and the independently derived `ENROLLED` disposition, so a class that exists but is not on the calculation route cannot satisfy the exception. The immutable commit changes only the gate and its S58 execution record; the scaffolded record is related to `2026-08-05-ci-lane-deconflation-plan`.

Independent checks passed: ruff, formatting, syntax compilation, the restored grouping gate (4 passed in 70.55s), and the adjacent calculation-route mesh parity suite (12 passed in 1.87s). No plan, policy, baseline, or production route was changed.

## Recommendations

Approve P02.S58. Keep future resolver-backed grouping exceptions source-kind keyed and route-enrolment proved; resolver construction alone is not a calculation path.
