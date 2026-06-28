---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S152'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S152 Core Meta-Test Repair

Scope: repair core external-constants meta-test path assumptions after test topology shifts.

## Description

- Pointed the external-constants TOML fixture read at the core package root instead of the moved tests directory.
- Updated repository-root derivation in `test_external_constants.py` after the core tests moved one level deeper.
- Updated file-permissions source scanning to resolve the core package root after the tests moved one level deeper.
- Updated remote-state guard, live-parity, and oracle test scan paths to the registry `tests` package.
- Reverified the declarations JSON MIME alias invariant against the current declarations facade.
- Pointed the file-permissions AST policy tests at `aeat.core.file_permissions` instead of the tests directory.

## Outcome

The core external-constants meta-test lane now resolves real project paths again and passes with the focused core configuration and size-budget tests.

## Notes

Verification passed for Ruff, compileall, 95 focused core/meta tests, 41 focused record-design tests, and the 2-test hard codebase size-budget guard. No skips, xfails, mocks, or fake test substitutes were introduced.
