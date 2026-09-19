---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2af2568f85465fe0d34ed99927623371273f4f9d144c767eed30cbefb01f9cef'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `W01.P01.S02 TUI import-linter boundary review`

## Scope

Independent review of `W01.P01.S02` against the accepted TUI architecture decision, research, live `.importlinter` changes, `dev/tests/test_importlinter_tui_boundaries.py`, the S02 execution record, and applicable architecture, quality, RAG, and worktree rules.

## Findings

### backend-source-expression-proof | medium | The mutation matrix does not prove the backend prohibition source expression

The backend-prohibition contract relies on both `cadrumo.*` and `cadrumo.entrypoints.*`, but its only negative case plants `cadrumo.entrypoints.cli.command -> cadrumo.entrypoints.tui`. That edge is rejected by the second expression even if the general `cadrumo.*` expression is removed or narrowed, so no mutation proves application, core, domain, adapter, LLM, shared-test, or other backend packages are actually covered. The same case does not independently prove the named MCP prohibition. The configuration appears semantically aligned with D11, and the accepted fixture plus one bite per contract passed, but the central backend breadth claim is not anti-tautologically exercised.

## Recommendations

- Add real temporary-graph rejection cases from at least one non-entrypoint backend package and MCP, retaining the existing CLI case, so removing either source expression makes the focused test red.
- Add a descendant-adapter edge to the launcher acceptance and non-launcher rejection matrix so both launcher ignore expressions are exercised rather than only the bare `cadrumo.adapters` import.

## Final re-review disposition

### backend-source-expression-proof | closed | Independent backend, MCP, and adapter-descendant proofs now bite

The mutation matrix now independently rejects `cadrumo.application.service -> cadrumo.entrypoints.tui`, `cadrumo.entrypoints.mcp.tool -> cadrumo.entrypoints.tui`, and the retained CLI edge. It separately accepts `cadrumo.entrypoints.tui.launcher.wiring -> cadrumo.adapters.persistence` and rejects the same adapter-descendant reach from `cadrumo.entrypoints.tui.app`, proving both launcher ignore expressions and the non-launcher prohibition. The S02 execution record preserves the exact live four-contract command with 4 kept, the exact integration test route with 8 passing tests, and the exact Ruff command with all checks passing.

No critical, high, or medium findings remain from this review.
