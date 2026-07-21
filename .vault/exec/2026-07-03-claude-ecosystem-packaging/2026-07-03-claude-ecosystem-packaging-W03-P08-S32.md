---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S32'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Test the CLI materialises a schema-valid plugin tree end-to-end to an output directory

## Scope

- `src/aeat/entrypoints/cli/tests/test_app_agent_plugin.py`

## Description

- Add `test_app_agent_plugin.py` proving the CLI's `--layout plugin` option materialises a schema-valid plugin tree end-to-end to an output directory.
- Absorb the pre-existing stale flat-path assertions in `test_app_agent_workspace.py` that the `--layout plugin` addition made incorrect (coordinator-approved in-scope regression fix, per the shared-worktree discipline of fixing regressions a campaign's own change touches).
- Commit `40712a6ffb`.

## Outcome

- New end-to-end plugin CLI test passes; the absorbed `test_app_agent_workspace.py` assertions are corrected rather than left red.

## Notes

No incidents. No skipped work.
