---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:4b4ac88d8ec9d42392f078dd30b5f43f768dae4d3e0d46b6c2bfdcdeb1d9eeb9'
step_id: 'S38'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Re-arm the MCP mirror for the accepted auth, certificate, and recovery verbs

## Scope

- `src/cadrumo/agent/`

## Description

- Re-arm the MCP mirror for the recovery family: the mirror derives its verbs from the risk table and the registered payload schemas, so the new `config.recovery.*` rows and schemas (and the removal of the retired ids) propagate it.
- Verify with the MCP suite including the per-verb CLI-vs-MCP schema-parity diff and gate-refusal tests.

## Outcome

MCP suite green (301 tests) over the accepted auth, certificate, and recovery verbs.

## Notes

No hand-authored MCP verb list exists for these families; the risk-table plus schema registry is the single mirror source.
