---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:53a7df0f436eed4ec5b84610fb2e166913d44122fba9c61b0275125ba0a1bede'
step_id: 'S10'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Author reviewed 2024-applicable legal catalogue entries and anchors for the closed worklist

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/is.toml`
- `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `verify:` `uv run pytest -n0 dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_measures_the_complete_2024_population_and_closes_reviewed_authority dev/registry/tests/test_m200_2024_full_reconciliation.py::test_modelo_200_orden_governed_period_is_verified_against_its_bundled_boe_text -q` -> `pass`
