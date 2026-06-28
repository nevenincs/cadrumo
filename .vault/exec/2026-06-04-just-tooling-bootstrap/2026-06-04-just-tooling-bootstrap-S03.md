---
tags:
  - '#exec'
  - '#just-tooling-bootstrap'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-just-tooling-bootstrap-plan]]'
---

# S03 Verify New Command Surface

Scope: `just tooling`.

## Description

- Confirm the new recipes appear in `just --summary`.
- Dry-run the aggregate audit recipes and representative leaf recipes.
- Verify the Python lockfile, representative audit tool versions, the Semgrep `uvx` fallback, and the pinned duplication scanner.
- Run the duplication audit once against production source with test and fixture paths ignored.
- Run dependency and dead-code advisory recipes once to confirm they execute and report existing findings.

## Outcome

The command surface is visible, parses successfully, and the duplication audit runs to completion with the pinned scanner. The Semgrep `uvx` fallback resolves a scanner executable. `audit-deps` reports 6 existing dependency issues, and `audit-dead-code` reports production dead-code candidates. The lockfile check passes.

## Notes

The shared virtual environment could not complete a full sync in this turn because an existing `vaultspec-rag.exe` process lock prevented replacement of that executable. A minimal no-deps repair restored `vaultspec-core`, `deptry`, and `vulture` spawning for this task; a later full sync should be run when the lock is released.
