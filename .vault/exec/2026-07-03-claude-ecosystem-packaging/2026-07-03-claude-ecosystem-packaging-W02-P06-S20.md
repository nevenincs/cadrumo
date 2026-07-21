---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S20'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add the corpus-sources optional extra pinning aeat-data at an exact version

## Scope

- `pyproject.toml`

## Description

- Add the `corpus-sources` optional extra to `pyproject.toml`, pinning `aeat-data==0.1.0` at an exact version.
- Deliberately exclude `corpus-sources` from the `all` aggregate extra until the companion distribution is published — including it would make `aeat[all]` unresolvable.
- Add a `[tool.uv.sources]` path source pointing at `packaging/aeat_data` so the dev resolver builds the companion locally, while published wheel metadata keeps the bare version pin.
- Teach `dev/packaging/smoke_core.py`'s `_export_names` to resolve local-path export rows via the referenced project's `[project].name`.
- Document the deptry `DEP002` suppression for the data-only package (reached dynamically via `importlib.resources`, carries no importable code).
- Commit `d04ec459ad`.

## Outcome

- `just packaging-smoke-dependencies` exits 0.
- `just check-dependencies` (deptry) exits 0.

## Notes

Executed inline by the coordinator during the executor-fleet rate-limit window. No incidents.
