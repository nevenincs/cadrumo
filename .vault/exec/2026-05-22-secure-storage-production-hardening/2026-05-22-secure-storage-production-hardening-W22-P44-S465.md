---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S465'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Assert `config switch` is mounted and `config unlock` is absent

## Scope

- `src/aeat/application/operator_surface/tests/test_contract.py`

## Description

- Re-read the D1 command decision and the live operator-surface contract.
- Confirmed the contract enumerates the custody command set exactly with `switch` and without `unlock`.
- Ran `uv run --no-sync pytest src/aeat/application/operator_surface/tests/test_contract.py -q`.

## Outcome

The existing production contract already enforces the D1 hard rename without a
duplicate test change: 15 operator-surface contract tests pass, including the
exact custody-command set assertion.

## Notes

No source or test edit was needed. Adding a second negative assertion would be
tautological because the existing equality assertion already proves that
`unlock` is not part of the command set.
