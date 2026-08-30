---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:4ec6130473135384ca16cbd7c2b9cbdaf9dbcb83cfdc40c570fa870964701d77'
step_id: 'S96'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Sweep the third stale-pin class: ruff per-file ignores in pyproject naming modules the retirements made public, deleting rather than repointing where a narrower inline suppression already covers the site

## Scope

- `pyproject.toml`

## Changes

- `M` `pyproject.toml`
- `verify:` `ruff check src/cadrumo/domain/deadlines src/cadrumo/application/wizard src/cadrumo/domain/auth/apoderamientos` -> `pass`

## Notes

The wizard entry is deleted rather than repointed: an inline `noqa` carrying a
stated reason already covered that one line, so the broader per-file ignore was
redundant and the narrower suppression is the correct one to keep.
