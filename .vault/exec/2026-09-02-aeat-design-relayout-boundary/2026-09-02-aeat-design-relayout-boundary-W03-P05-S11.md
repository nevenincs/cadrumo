---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:16dea4f25a3d1c1e11d4a58bd7a5dda839a1412af1ff97404638ecf3a6884d45'
step_id: 'S11'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# Enforce legal resolution, target-window coverage, anchor reachability, and rejection of later-year substitution

## Scope

- `dev/registry/tests/test_m200_2024_full_reconciliation.py`

## Changes

- `M` `dev/registry/analysis/m200_2024_full_reconciliation.py`
- `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `verify:` `uv run pytest -n0 dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_measures_the_complete_2024_population_and_closes_reviewed_authority dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_refuses_missing_unknown_wrong_and_later_year_authority dev/registry/tests/test_m200_2024_full_reconciliation.py::test_cli_legal_admission_refuses_an_open_worklist_and_pending_authority -q` -> `pass`
