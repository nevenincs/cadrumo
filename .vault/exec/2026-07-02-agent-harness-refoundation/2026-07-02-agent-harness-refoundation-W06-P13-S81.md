---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S81'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Expose the corpus search MCP tool

## Scope

- `src/aeat/entrypoints/mcp/_corpus_tools.py`

## Description

- Corpus search MCP tool. `_corpus_tools.py` (SDK-independent payload/render + build_corpus_search_tool, readOnly/idempotent annotations) was authored by the grounding executor; the coordinator wired it into `_server.py` (advertised in _list_tools, routed in _call_tool with graceful tool-error handling on a missing index / degraded mode / bad query). Smoke: server builds, tool advertised.

## Outcome

Closed on green gates: mcp + corpus_search lane 161 passed; ruff clean.
Split-authorship honestly recorded (application layer + resources + tests by
the grounding executor before its session limit; MCP tool wiring + facade
exposure by the coordinator).

## Notes

The grounding executor hit its session limit mid-W06.P13; the coordinator
finished the MCP wiring per the operator directive that hard technical work
is coordinator-owned.
