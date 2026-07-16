---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S223'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Re-arm MCP identity confirmation when canonical profile logout clears the active taxpayer

## Scope

- `src/cadrumo/entrypoints/mcp/_identity_gate.py`
- `src/cadrumo/entrypoints/mcp/tests/test_identity_gate.py`

## Description

- Define one closed set of active-identity-changing commands.
- Include canonical profile logout because it clears the active taxpayer identity.
- Prove pure, direct-tool, and meta-execute paths re-arm the identity gate before the next mutation.

## Outcome

Both MCP dispatch paths require a fresh identity read after strong logout, preventing a later mutation from proceeding under an unconfirmed taxpayer context.

## Notes

The focused MCP identity suite completed with 15 passing tests.
