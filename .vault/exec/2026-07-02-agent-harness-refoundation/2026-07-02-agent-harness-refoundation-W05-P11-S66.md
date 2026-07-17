---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S66'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add the regularizar-atrasos golden scenario

## Scope

- `src/aeat/agent/eval/scenarios/regularizar_atrasos.toml`

## Description

- Read the eval runner contract in full before authoring: trajectory keys must
  resolve via `command_schema_refs()`, lifecycle order binds only the
  modelo.work stages present, and every trajectory verb's CLI form must appear
  verbatim in the owning skill's text.
- Probe the registry: 303/2024/1T resolves with a grounded verification
  contract carrying casillas 64/66; all five overview keys plus
  `modelo.work.amend` resolve as command keys.
- Author `src/aeat/agent/eval/scenarios/regularizar_atrasos.toml`: trajectory
  is the situation skill's own driven surface (`overview.status`,
  `overview.backlog`, `overview.explain`); the delegated catch-up spine stays
  covered by the per-modelo scenarios.

## Outcome

Scenario authored by the coordinator; the all-scenario sweep
(`test_modelo_130_golden.py`, 9 passed) includes and passes it. Commit
`229127db6`, exactly one file.

## Notes

The wider eval lane showed ~26 concurrent failures at authoring time
(replay/under-declaration/exit-code tests) consistent with the W01 executor's
in-flight edits to the MCP dispatch surface — signature reported to that
executor, whose wave gate was extended to the full
`src/aeat/entrypoints/mcp src/aeat/agent` lane. Not absorbed here: this
Step's sweep is green in isolation.
