---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:2d891704196832dd7d8ba9ddc8f5708273e16c18117177caa6c510961db4d128'
step_id: 'S05'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Implement the source-SHA-bound planner and canonical TOML mutation surface for 3,171 exact map-owned declaration rebinds while refusing two true orphans

## Scope

- `dev/registry/analysis/m200_2024_full_reconciliation.py`

## Changes

- `M` `dev/registry/analysis/m200_2024_full_reconciliation.py`
- `verify:` `uv run --no-sync python -m pytest -n 0 dev/registry/tests/test_m200_2024_full_reconciliation.py -q` -> `pass`
