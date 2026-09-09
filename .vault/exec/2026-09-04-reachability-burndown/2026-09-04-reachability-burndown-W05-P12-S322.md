---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d98486ca9a818897d62d0aa8adb39eb950051598187906ddab3ef19733d37126'
step_id: 'S322'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove invoice-kind singularity owner strings and embedded mapping implementations

## Scope

- `live invoice-kind decision scan`
- `aggregation behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/tests/test_invoice_kind_singularity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_invoice_kind_singularity.py src/cadrumo/application/aggregation/tests/test_non_arising_category_side_is_refused.py` -> `pass`
