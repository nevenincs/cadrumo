---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:28edb0b194d9862c422fcc516989f33fd1211b69ce46b445007c87e98db1a830'
step_id: 'S01'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

# Add sphinx-intl and babel to the docs dependency group, refresh the lockfile, and verify both import under uv

## Scope

- `pyproject.toml`
- `uv.lock`

## Description

- Add `sphinx-intl>=2.3` and `babel>=2.16` to the `dev` dependency group alongside the existing Sphinx cluster, with a comment stating `sphinx-intl` manages the per-language catalogues and `babel` parses catalogue statistics for the completeness gate.
- Refresh the lockfile with `uv lock` and reconcile the environment.
- Verify both packages import under `uv run --no-sync python`.

## Outcome

`sphinx-intl` 2.3.2 and `babel` 2.18.0 resolve and import cleanly. `babel` was already a transitive Sphinx dependency; the lock now pins both as declared docs tooling.

## Notes

The environment sync pruned four undeclared leftover packages (`pytest-httpx`, `pytest-rerunfailures`, `syrupy`, `time-machine`). They are not declared in the manifest and are members of the test-suite banned-live-imports gate, so removal reconciled the venv to the lock with no impact on collection.
