---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Prove installed-mode storage resolves off the platform directory and never off PROJECT_ROOT with a fresh-install roundtrip test

## Scope

- `src/aeat/core/tests/test_config_state_root.py`

## Description

- Add a fresh-install roundtrip test to `src/aeat/core/tests/test_config_state_root.py` proving installed-mode resolution lands under the platform user-data directory and never under `PROJECT_ROOT`.
- Confirm the checkout default is unchanged by the same proof.
- Add an anti-tautology case: repo markers (a `pyproject.toml` file plus a `.git` path) beat a populated `LOCALAPPDATA` environment variable, so a checkout is never mistakenly routed to the platform directory.
- Exercise the real `Settings` validator chain end to end; no mocks, fakes, or monkeypatches.
- Commit `196058bb29`.

## Outcome

- Full-suite collect-only gate (`uv run --no-sync pytest --collect-only -q`) clean across 265 collected items.

## Notes

No incidents. No skipped work.
