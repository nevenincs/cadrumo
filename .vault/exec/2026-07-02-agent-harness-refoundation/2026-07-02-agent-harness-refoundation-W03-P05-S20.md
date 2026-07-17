---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S20'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Enforce the CONFIRM tier through elicitation in the call-tool path

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Wire the elicitation-backed CONFIRM tier into the direct call path: negotiated client capability read fail-closed from the request context; ELICIT route performs the real session.elicit round-trip with the localized one-boolean confirmation; every non-explicit-yes outcome refuses with a localized declined message; REFUSE routes emit the localized refusal texts; the meta-execute path runs the same matrix with client_supports_elicitation=False (a sync callable cannot elicit), so a handoff-tier meta call fails closed.

## Outcome

Authored by the coordinator (commit `2ba6d656f4`, shared with the sibling
step — the two steps are one cohesive serving-path edit). MCP + locale
suites green at commit: 105 passed, scaffold --check clean, honesty gate
green with genuine es/ca/hu translations for the new declined key.

## Notes

None.
