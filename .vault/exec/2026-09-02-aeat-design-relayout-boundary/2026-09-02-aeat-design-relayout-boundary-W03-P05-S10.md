---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:de97d7fd80f0a5d747c25a277cc78a6b4c58c2ca53bbd4696da88abbd56262a0'
step_id: 'S10'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# Author reviewed 2024-applicable legal catalogue entries and anchors for the closed worklist

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/is.toml`
- `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `verify:` `uv run pytest -n0 dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_measures_the_complete_2024_population_and_closes_reviewed_authority dev/registry/tests/test_m200_2024_full_reconciliation.py::test_modelo_200_orden_governed_period_is_verified_against_its_bundled_boe_text -q` -> `pass`
