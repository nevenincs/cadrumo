---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S12'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Build the scripted intent driver preserving the canonical-answer underflow and overflow drift detection

## Scope

- `src/cadrumo/application/flows/_scripted.py`

## Description

- Drive the engine from a scripted sequence of canonical answers, preserving underflow detection (script exhausted before the walk completes) and overflow drift detection (answers left unconsumed).
- Feed the same engine contract the interactive frontends use so scripted and interactive paths cannot diverge.
- Landed in `26615cd4e6`; exercised by the wizard harness rewrite `d0d47b8730` that drives the harness through the substrate contract.

## Outcome

The scripted driver replays a fixed answer script through the engine and fails loudly on under- or over-supply, giving deterministic headless coverage for the migrated consumers.

## Notes

None.
