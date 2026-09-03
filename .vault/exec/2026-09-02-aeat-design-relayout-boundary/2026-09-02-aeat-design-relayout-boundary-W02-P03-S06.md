---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:2d3f14b11036ef86bc6ae556055f5c6657dc84d73a64df0af415afe563ce9bbf'
step_id: 'S06'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Reject missing anchors, source drift, duplicate output, altered non-source payloads, and partial rebind application

## Scope

- `dev/registry/tests/test_m200_2024_full_reconciliation.py`

## Changes

- `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `verify:` `uv run --no-sync python -m pytest -n 0 dev/registry/tests/test_m200_2024_full_reconciliation.py -q` -> `pass`
