---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:53feddebbaaa39add3cf816bd2040c5553cf89dfda14f96b97112494f835884e'
step_id: 'S06'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add the search-plus-execute meta-tool pair for verbs outside the curated toolsets

## Scope

- `src/aeat/entrypoints/mcp/_meta_tools.py`

## Description

- Add `_meta_tools.py` with `search_commands` ranking the command surface against a query by command-key and description token overlap, returning typed results carrying each verb's read-only and destructive hints.
- Add `gate_refusal` as the single gate sequence (persona scope, then the permanent live-write block) producing refusals byte-identical to the direct call path.
- Add `meta_execute` resolving a command key, applying `gate_refusal`, and dispatching only on a clear gate through an injected runner, so the module stays SDK-independent.

## Outcome

`search` ranks a named verb above one that merely mentions the query (`modelo.iva_wallet.balance` scores highest for "iva wallet balance"), and `execute` is verified to route through the same gates as a direct call: `gate_refusal` returns exactly the direct path's persona-scope refusal for every out-of-scope key under a given persona, `meta_execute` never reaches its runner on a refused or unknown command, and it dispatches only when the gate clears. Ruff check/format clean, pyright clean, and the mcp suite is green at 61 passed.

## Notes

The execute gate reproduces the CURRENT server behaviour: persona-scope refusal plus the permanent live-write BLOCK. The CONFIRM tier is intentionally not enforced here (nor on the direct path today); that is W03 elicitation work. Keeping `gate_refusal` the single sequence both paths share is what makes the meta-tool safe - a verb outside the active persona cannot be reached by naming it to `execute`.
