---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S27'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add a real-client handshake conformance test exercising initialize, tools-list, and a call round-trip over stdio

## Scope

- `src/aeat/entrypoints/mcp/tests/test_client_handshake.py`

## Description

- Add `test_client_handshake.py` proving a real MCP client can initialize, list tools, and round-trip one read-only call.
- Drive the in-process memory transport against `build_server` for a deterministic floor: initialize, list tools (floor plus meta plus verbs present), then a `contract` read-only call returning a non-error envelope with the contract command.
- Drive a true `aeat-mcp` server subprocess over stdio through the live harness with a scripted persona calling the harness floor tool, asserting one non-error call whose result carries the operating-layer text.

## Outcome

Both handshake tests pass: the in-process client negotiates and round-trips a read-only call deterministically, and the stdio subprocess client completes the same initialize / tools-list / call round-trip over the real transport, returning the operating layer from the floor tool. Ruff check/format clean.

## Notes

The stdio test spawns a fresh interpreter running `from aeat.entrypoints.mcp import main; main()`; the live harness merges the parent environment into the subprocess parameters so PATH and the interpreter resolve, and the read-only floor tool needs no profile or secret store, so the round-trip is self-contained. The subprocess spawn makes this the slower test in the file, but it is the real-transport conformance the in-process test alone cannot prove.
