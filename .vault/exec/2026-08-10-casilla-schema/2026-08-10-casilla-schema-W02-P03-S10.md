---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e154df6bb78088a50ea96503a8e650f837262f37ead3c2a3968d31adfe385211'
step_id: 'S10'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Retarget M390 M303 reconciliation to the canonical reverse join

## Scope

- `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `src/cadrumo/application/modelo/tests/test_calculation_modelo_adjustments.py`

## Description

- Replace the local primary-only, last-write binding map with the public `casillas_by_binding` authority.
- Carry every target casilla associated with a relation binding into the silent-zero refusal context.
- Prove a real bundled M390 relation remains reachable when its target binding is present only as an alternate binding.
- Run focused behavioral, lint, format, type, structural, and diff checks and obtain an independent formal review.

## Outcome

- M390-to-M303 reconciliation now consumes the canonical reverse join and preserves all target casillas.
- The focused regression passed, and the formal S10 audit reported PASS with no findings.
- Production and test changes landed in `287f770a30`.

## Notes

- Commit `287f770a30` also absorbed unrelated peer-owned ledger and registry-test work. Rewriting shared history would risk data loss, so this record names the actual landing commit and preserves the atomicity exception explicitly.
- The older reconciliation end-to-end fixture remains independently red because it pins removed revision `2023-y-siguientes`; current registry revisions use `2023`, split 2024 revisions, 2025, and 2026 onward. The focused S10 behavior does not traverse that stale fixture.
