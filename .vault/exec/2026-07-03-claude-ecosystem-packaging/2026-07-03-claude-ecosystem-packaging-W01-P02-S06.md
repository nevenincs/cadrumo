---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Confirm deptry and the packaging-smoke dependency-surface gate stay clean after the demotion

## Scope

- `dev/packaging/dependency_surface.py`

## Description

- Verify both dependency gates after the S05 demotion; prove via a git-archive HEAD extract that both were ALREADY red on pristine HEAD (six leaked core packages on the packaging-smoke dependency-surface check; two deptry findings).
- Confirm the S05 demotion resolved every `vaultspec-rag`-specific finding.
- Absorb the two pre-existing residuals on coordinator routing: commit `2048676be5` adds the `_CORE_PRESENT_TRANSITIVE_NAMES = {"numpy"}` carve-out in `dev/packaging/smoke_core.py` (numpy is a base dependency of `formulas` name-colliding with the `search` extra); commit `aa1d68abc3` declares `anyio>=4.5,<5` in the `agent` optional extra (directly imported by the MCP server, previously only transitively satisfied via `mcp`), refreshes `uv.lock`, and extends the carve-out to `{"numpy", "anyio"}` (the same transitive-name collision via `httpx`).

## Outcome

- `just packaging-smoke-dependencies` exits 0 ("dependency surfaces verified", 7 optional extras, 12 optional deps); `just check-dependencies` (deptry) exits 0. Both gates fully green — closing pre-existing reds beyond the step's own scope, per the absorb-in-scope-regressions discipline.

## Notes

The step produced three commits rather than one: the gate-verification finding was routed to the coordinator, which directed absorbing both pre-existing residuals since the W04 release lane requires these gates green. `formulas` was deliberately NOT demoted (behavioural change beyond scope); the carve-out documents the collision instead.
