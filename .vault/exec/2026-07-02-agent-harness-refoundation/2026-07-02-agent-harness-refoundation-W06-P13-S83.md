---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S83'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Expose the terminology handbook search tool

## Scope

- `src/aeat/entrypoints/mcp/_terminology_tools.py`

## Description

- Terminology handbook tool. The application-layer `_terminology.py` (search_terminology/lookup_terminology over approved-lifecycle concepts) existed but was unexposed; the coordinator added the facade exports and authored `_terminology_tools.py` (the aeat_terminology_search MCP tool) and wired it into the server. Smoke: search "prorrata" -> prorrata, prorrata-especial.

## Outcome

Closed on green gates: mcp + corpus_search lane 161 passed; ruff clean.
Split-authorship honestly recorded (application layer + resources + tests by
the grounding executor before its session limit; MCP tool wiring + facade
exposure by the coordinator).

## Notes

The grounding executor hit its session limit mid-W06.P13; the coordinator
finished the MCP wiring per the operator directive that hard technical work
is coordinator-owned.
