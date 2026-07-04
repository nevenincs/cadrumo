---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S01'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add an installed-vs-checkout detector and a platform user-data root resolver (LOCALAPPDATA on Windows, XDG_DATA_HOME on Linux, Application Support on macOS)

## Scope

- `src/aeat/core/_config_state_root.py`

## Description

- Add `src/aeat/core/_config_state_root.py`, a stdlib-only module resolving the installed-vs-checkout distinction and the platform user-data root.
- Detect checkout mode when a `PROJECT_ROOT` candidate carries a `pyproject.toml` file AND a `.git` path (checked with `.exists()` deliberately, since a git-worktree `.git` is a pointer file, not a directory); otherwise treat the run as installed.
- Resolve the platform user-data base: Windows `%LOCALAPPDATA%` with a `~/AppData/Local` fallback; Linux `$XDG_DATA_HOME` with a `~/.local/share` fallback; macOS `~/Library/Application Support`; append the `aeat` app directory. Ignore a relative env value per the XDG spec.
- Model the resolution as a typed frozen pydantic seam: `StateRootInputs` -> `resolve_state_root(...)` -> `StateRootResolution`. `live_state_root_inputs()` snapshots the live process state; `default_storage_root()` is the config-bound factory that consumes it.
- Commit `90de29329f`.

## Outcome

- `ruff check` clean on the new module.
- 10 unit tests passed for the detector and resolver.
- `python -m dev.docs.apidocs scaffold --check` conformant: no stub delta, since the module is private with no public re-export.

## Notes

No incidents. No skipped work.
