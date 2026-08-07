---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:28f96ef85fa8c4d117b0c22d80a6fb025612e6bcaac0b4f3fa956403f0256152'
step_id: 'S03'
related:
  - "[[2026-08-05-arch-remediation-registry-format-plan]]"
---

# Record in the workbook parity gate docstring that section order is deliberately unasserted, so a future reader does not re-add the claim from the rule history

## Scope

- `src/cadrumo/application/storage/calc_sheets/tests/test_modelo_export_parity.py`

## Description

- Add a docstring to the workbook parity gate naming the three properties it enforces.
- State that section order is deliberately unasserted, and why a reader should not re-add it.

## Outcome

The gate now documents its own scope at the point where a future reader meets it.
The paragraph names the omission explicitly and gives the reason it is an omission
rather than a gap: section is presentation, the casilla set and numbering are the
properties that must mirror the official modelo, and both are gated above.

It also records that a project rule previously claimed this gate enforced section
order and that the claim was corrected rather than satisfied - so a reader who
finds that history does not treat it as authority to add the assertion.

## Verification

The gate still passes with the docstring in place:

    uv run --no-sync pytest -q -p no:randomly src/cadrumo/application/storage/calc_sheets/tests/test_modelo_export_parity.py
    9 passed in 16.35s

## Notes

Docstring only; no assertion was added or removed, so the gate's behaviour is
unchanged and the 9-test result is the same selection as before the edit.
