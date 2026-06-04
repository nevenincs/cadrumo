---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
step_id: 'S123'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P17.S123` internal service coverage verification

Step scope: `src/aeat/application`.

## Description

- Audit application selector, work-addressing, export, reconcile, history, taxation comparison, result-summary, and projection linkage.
- Verify command-specific revision defaults live behind application services.
- Verify direct tests cover visible-target lookup, current pointers, filed/exportable defaults, and address-based adjacent services.

## Outcome

Internal service coverage is present:

- `src/aeat/application/modelo/_selectors.py` owns visible-target lookup, ambiguity/refusal types, pointer selectors, and exportable selection.
- `src/aeat/application/modelo/_revision_persistence.py` preserves current and filed pointer persistence.
- `src/aeat/application/modelo/_taxation_comparison.py` exposes address-based taxation comparison.
- `src/aeat/application/modelo/_history.py`, `_result_summary.py`, `_reconcile.py`, and `_export.py` remain the backend homes for their respective read and action flows.
- `src/aeat/application/state_projection.py` remains covered for state projection
  linkage while exact modelo IDs stay internal to application/domain records.

Focused verification passed:

- `.venv\Scripts\python.exe -m pytest -q src/aeat/application/modelo/test_selectors.py src/aeat/application/modelo/test_history.py src/aeat/application/modelo/test_reconcile.py src/aeat/application/modelo/test_taxation_comparison.py`
  passed `33` tests.
- `.venv\Scripts\python.exe -m pytest -q src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_export.py`
  passed `45` tests.
- `.venv\Scripts\python.exe -m pytest -q src/aeat/application/test_state_projection.py`
  passed `15` tests.

## Notes

- No mocks, fakes, skips, or xfails were used in the focused application
  verification.
- An additional exploratory run including
  `src/aeat/application/modelo/test_modelo_filing_snapshot_coverage.py` had two
  failures in the helper transaction fixture (`90.00 + 18.90 != 121.00`). That
  file is outside the planned S123 ID-linkage gate and is recorded here as
  unrelated residual risk, not as closure evidence for this step.
