---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b7de551ffddb139aa98d3aac44ec58cabd330d4247ed553172d866bbb427617c'
step_id: 'S19'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Modelo parity rollup S19 schema and reverse invariant closure

## Description

- Verify that every formula target resolves to a declared casilla.
- Enforce computed-casilla and formula-producer parity in the registry validator.
- Preserve exact formula identifiers across formula declarations and casilla producer declarations.

## Outcome

The accepted reverse-wiring contract is live in the registry validator. The real M100 wiring contract suite passed 8 tests, including the registry-wide inventory and failure cases for manual formula targets, missing reverse references, computed casillas without producers, noncomputed casillas with formula declarations, and duplicate targets.

## Notes

No semantic M100 2025 producer was added. The contract closes structural drift while keeping unresolved legal meaning and the SOL-deferred M100 rows outside this step.
