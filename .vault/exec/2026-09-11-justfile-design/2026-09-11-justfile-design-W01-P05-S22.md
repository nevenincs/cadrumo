---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:00d233ecee05c6a38e65315413dc19d9d19007e47ae58132fa4caf6973eb7b10'
step_id: 'S22'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Replace flat static checks with code and repository subject aggregates

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `M` `dev/quality/suite.py`
- `M` `dev/quality/tests/test_suite_gate_table.py`
- `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/quality/tests/test_suite_gate_table.py` -> `pass`
- `verify:` `just --dry-run check-code` -> `pass`
- `verify:` `just --dry-run check-repository` -> `pass`

## Notes

- `check-workflows` uses the existing `dev/actionlint.py` provisioner, which can write a cached executable when `actionlint` is absent; the read-only correction remains an integration dependency outside this lane's owned Python surfaces.
