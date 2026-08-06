---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:0561a74b152f2f86d6f3bfa34ec9fb42e1eb823a2628fd175ffd58ab753530c5'
step_id: 'S08'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Gate the table for completeness across every IvaCategory member and for non-divergence from the frozensets it derives from

## Scope

- `src/cadrumo/domain/iva/tests`

## Description

Coordinator adjudication (invoice-adr, 2026-08-05): work executed by the `iva-component-axis` / `income-grounding` lanes and landed before this record was written; the author is weekly-limited, so this body is written from verification at HEAD rather than by the executing agent. The coordinator (team-lead) independently verified the work DONE at HEAD; this record closes the honest gap between the landed work and its empty scaffold.

## Outcome

DONE, landed at `8585c78fd3` and extended by `1e61fc0d74`, which updated the completeness gate to cover every valid (IvaCategory, invoice kind) PAIR when the table was re-keyed — the pair-completeness upgrade the coordinator's ticket named as the silent-under-checking hazard. Verified at HEAD by one targeted probe: `src/cadrumo/domain/iva/tests/test_component_expectations.py` exists with 33 tests, covering completeness across the member set and non-divergence from the frozensets the table derives from (the import-time guard in `_components.py` is additionally an always-on backstop for the divergence half).

## Notes

One gate weakness in this test module was found AFTER landing by the P02.S21 code review (`test_weakly_grounded_retencion_expectations_carry_their_caveat` short-circuits on `BUNDLED_CORPUS`, the carve-out-guard-lost HIGH finding); its fix is in flight on the S21 revision lane and belongs to that Step's closure, not this one. This record attests the gate as landed for THIS Step's requirement (completeness + non-divergence), which the finding does not touch.
