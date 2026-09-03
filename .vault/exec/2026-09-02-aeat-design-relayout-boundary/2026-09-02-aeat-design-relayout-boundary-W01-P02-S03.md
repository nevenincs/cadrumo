---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:a79f251b029feda793df63a93073fe84a550e4dc4900f461aec289e74e2e7b16'
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
- The semantic-map source reference and SHA-256 must exactly match the parsed pinned design source before historic evidence is joined.
- Review output is revalidated at write time and written through a validated file handle, so a parent-directory swap during evidence generation cannot redirect bytes into registry authority.
- The opened output handle must be a regular file with exactly one link, with that link count rechecked immediately before truncation; new outputs use exclusive creation.
