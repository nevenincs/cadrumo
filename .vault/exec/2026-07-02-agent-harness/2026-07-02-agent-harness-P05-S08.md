---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:2f3b218f731f753382eb51f5113c132a68815649ac1d1d03b19f3f5158eae1bf'
step_id: 'S08'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit 198e6d6c7) - declare the runtime manifest-read persona-scope filter and its build-time pinning test asserting each persona's (family, mutability) ceiling resolves against the live contract

## Scope

- `src/aeat/entrypoints/mcp/_persona_scope.py`

## Description

- Declare `src/aeat/entrypoints/mcp/_persona_scope.py`, a runtime filter
  reading `aeat app contract --format json` and narrowing the tool set by
  the active persona's declared `(family, mutability)` ceiling.
- Add a build-time pinning test asserting each persona's declared ceiling
  resolves against the live contract.

## Outcome

Landed in commit `198e6d6c7`. At this commit the filter was declared and
unit-tested in isolation but had no live call site inside the MCP
`PreToolUse` dispatch path - functionally dead code at this Step's landing.
Closed by `P05.S09`.

## Notes

Flagged as the CRITICAL `d1-dead-code-now-resolved` finding in
`2026-07-02-agent-harness-content-review-audit`; resolved by the wiring Step
below, not by this Step alone.
