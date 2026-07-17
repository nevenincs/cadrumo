---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S22'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add a field-flows test proving the provisional percentage actually reduces the deducible cuotas for a prorrata taxpayer (the apportionment bites, not dead wiring)

## Scope

- `src/aeat/application/aggregation/tests/test_iva_ledger_prorrata_apportionment.py`

## Description

- Ground S22 with semantic search against the prorrata apportionment field-flow
  surface, then confirm exact binding ids and register provenance symbols with
  targeted grep.
- Add a real repository-backed regression that records one fully taxable sale
  and one fully taxable purchase, captures the baseline IVA ledger binding
  values with no prorrata register, records an active `general` register entry
  with a carried prior definitive provisional percentage, and re-runs the same
  aggregation plus binding resolver path.
- Assert the prorrata apportionment carrier is present, the deducible cuota
  binding is lower than the baseline value, the matching deducible base binding
  is unchanged, and an output IVA cuota binding is unchanged.
- Record the S22 implementation review in the feature audit with no open
  findings.

## Outcome

- The S22 regression proves the provisional percentage is live wiring: it bites
  on the deducible cuota binding for a prorrata-general taxpayer, while bases
  and devengado cuotas stay outside the apportionment.
- The test uses the shared encrypted repository and resolver surfaces already
  used by the application path, with the pre-prorrata run as the comparison
  oracle rather than a duplicate hand-computed formula.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\application\aggregation\tests\test_iva_ledger_prorrata_apportionment.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\aggregation\tests\test_iva_ledger_prorrata_apportionment.py -n 0` (2 passed).
