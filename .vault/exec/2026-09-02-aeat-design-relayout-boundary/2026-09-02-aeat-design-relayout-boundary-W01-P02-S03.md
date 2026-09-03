---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0d5e142aff75aedc4b22ee1fc903aa93a56606f0ff2f269b57b6ba7d7ec57d24'
step_id: 'S03'
related:
  - "[[2026-09-02-modelo-200-semantic-crosswalk-plan]]"
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
