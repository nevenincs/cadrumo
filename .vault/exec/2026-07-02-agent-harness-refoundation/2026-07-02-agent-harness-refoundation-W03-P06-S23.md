---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S23'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Wire faithfulness into the serving path as an advisory notice with a hard block at the export and record-marker boundary

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Wire the session grounding window, arguments-faithfulness (advisory content prepended on mismatch; hard block at the handoff), the per-verb handoff deny (list-time filtering + call-time refusal), and payload-free telemetry (route labels incl. elicit outcomes and faithfulness_block; hash-only argument/result references) into both the direct and meta-execute serving paths. The stdio runner mints the session id and injects the telemetry writer; unit builds stay hermetic with telemetry=None.

## Outcome

Authored by the coordinator (commit `2ba6d656f4`, shared with the sibling
step — the two steps are one cohesive serving-path edit). MCP + locale
suites green at commit: 105 passed, scaffold --check clean, honesty gate
green with genuine es/ca/hu translations for the new declined key.

## Notes

None.
