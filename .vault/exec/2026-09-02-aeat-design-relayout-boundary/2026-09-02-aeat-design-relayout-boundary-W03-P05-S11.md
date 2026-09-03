---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:863d9323eee9a8c17c7506ce92f08dd5981e96c86fe9d821bb8e7bb2b8d79370'
step_id: 'S11'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Enforce legal resolution, target-window coverage, anchor reachability, and rejection of later-year substitution

## Scope

- `dev/registry/tests/test_m200_2024_full_reconciliation.py`

## Changes

- `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `verify:` `uv run pytest -n0 dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_measures_the_complete_2024_population_and_closes_reviewed_authority dev/registry/tests/test_m200_2024_full_reconciliation.py::test_modelo_200_orden_governed_period_is_verified_against_its_bundled_boe_text dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_refuses_missing_unknown_wrong_and_later_year_authority -q` -> `pass`
