---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:49a12d078503460a6ee0ae8cf2eeb8cb45dda4c6c12b73a878bc2d5b461ae0c7'
step_id: 'S31'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add a claude plugin validate --strict packaging gate that runs against a freshly materialised plugin when the claude CLI is on PATH and skips honestly when it is not (verify the validate flag against live official docs at execution time)

## Scope

- `dev/packaging/smoke_plugin_validate.py`

## Description

- Add `dev/packaging/smoke_plugin_validate.py`, materialising a fresh plugin tree and running `claude plugin validate --strict` against it when the `claude` CLI is on `PATH`.
- Verify the `validate --strict` flag against the live official docs at execution time, per the plan's frontier-surface directive.
- Skip honestly, naming the missing tool, when the `claude` CLI is absent rather than silently passing.
- Commit `2788f3d382`.

## Outcome

- The smoke lane reports an explicit `SKIPPED` status naming the missing tool on a machine without the `claude` CLI, and a real strict-validate pass on a machine with it.

## Notes

No incidents. No skipped work.
