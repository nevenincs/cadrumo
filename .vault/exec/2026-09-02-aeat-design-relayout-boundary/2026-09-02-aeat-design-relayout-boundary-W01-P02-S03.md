---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:385074c884395dfd060a75e494059a2a1ae525e4418548c1c0e53a822450bbca'
step_id: 'S03'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# Retire historic-payload restoration as authority-producing behavior while retaining proposal-only diagnostics

## Scope

- `dev/registry/analysis/m200_2024_restoration_candidates.py`

## Changes

- `M` `dev/registry/analysis/m200_2024_restoration_candidates.py`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/m200_2024_restoration_candidates.py` -> `pass`

## Notes

- Remediation rejects every review destination whose lexical or resolved path is within the canonical registry root, including traversal and symlink containment.
- Removed the unused historic-candidate compatibility alias and builder; the proposal-only API is now the sole exported surface.
