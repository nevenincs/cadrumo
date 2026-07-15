---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S47'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Prove a real Cadrumo client initialize, list, call, and shutdown handshake

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_client_handshake.py`

## Description

- Spawn the installed/current `cadrumo-mcp` executable through the real MCP stdio client.
- Initialize the session and enumerate resources, resource templates, prompts, and tools.
- Assert canonical Cadrumo identities and reject the former product identity across every wire surface.
- Call the shipped read-only harness tool and close both client and subprocess contexts cleanly.

## Outcome

The live handshake proves the Cadrumo server name, `cadrumo://` resource
identity, `cadrumo-empezar` orientation prompt, `cadrumo_` tool identity, a
successful safe tool round trip, and orderly shutdown. Both focused integration
tests and Ruff checks pass.

## Notes

The existing in-process probe originally called the CLI-backed contract tool,
which intermittently depended on a second executable being present on `PATH`.
It now calls the same shipped read-only harness floor as the stdio proof, keeping
the test focused on MCP transport behavior without substitutes.
