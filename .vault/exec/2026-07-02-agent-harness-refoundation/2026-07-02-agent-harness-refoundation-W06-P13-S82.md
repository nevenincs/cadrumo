---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S82'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add aeat corpus ref resources resolving citations to verbatim authoritative text

## Scope

- `src/aeat/entrypoints/mcp/_resources.py`

## Description

- aeat://corpus/{ref} resource. The corpus resource template + read handler live in `_resources.py` (grounding executor); verified end-to-end: `aeat://corpus/ley-58-2003:art-27.2` resolves to 2144 chars of verbatim LGT art. 27 text as text/markdown. Four templates now serve: skill/rule/persona/corpus.

## Outcome

Closed on green gates: mcp + corpus_search lane 161 passed; ruff clean.
Split-authorship honestly recorded (application layer + resources + tests by
the grounding executor before its session limit; MCP tool wiring + facade
exposure by the coordinator).

## Notes

The grounding executor hit its session limit mid-W06.P13; the coordinator
finished the MCP wiring per the operator directive that hard technical work
is coordinator-owned.
