---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:ebeecba038121ef0dd99f6ca8afb016cb14b48a8ce6761297bf2d1da3ad79fbb'
step_id: 'S11'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# Enforce legal resolution, target-window coverage, anchor reachability, and rejection of later-year substitution

## Scope

- `dev/registry/tests/test_m200_2024_full_reconciliation.py`

## Changes

- `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `verify:` `uv run pytest -n0 dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_measures_the_complete_2024_population_and_closes_reviewed_authority dev/registry/tests/test_m200_2024_full_reconciliation.py::test_modelo_200_orden_governed_period_is_verified_against_its_bundled_boe_text dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_refuses_missing_unknown_wrong_and_later_year_authority -q` -> `pass`
