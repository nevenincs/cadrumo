---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7ad578fae6850b8661a19e108680aa0c075be20cd58d02f5811767554e3403d0'
step_id: 'S37'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Export the filed-history operation definition through the live application facade

## Scope

- `src/cadrumo/application/live/__init__.py`
- `src/cadrumo/application/live/tests/test_filed_history_operation_facade.py`

## Description

- Replace the live facade's ad-hoc lazy resolution ladder with its canonical literal manifest and shared lazy loaders.
- Export the filed-history definition identity, strict request contract, and dependency-composed definition builder through the live facade.
- Keep the concrete executor, injected pull seam, phase constants, and orchestration helpers private to their owning module.
- Add real facade contract coverage for canonical origins, definition metadata, lazy loading, public-name resolution, and private-internal exclusion.

## Outcome

The live application facade now exposes the filed-history operation's public
definition contract without eagerly importing its executor module. The facade
manifest preserves the existing lazy service exports, and the new contract
exports resolve to the canonical operation module. Focused facade and filed-
history integration tests pass, as do Ruff formatting/lint, BasedPyright, and
the repository facade scan.

## Notes

The direct facade-scan script requires module execution because it imports the
`dev` package; its canonical module invocation passed with zero forward or
mirror breaks. No plan-state mutation or unrelated worktree change was made.
