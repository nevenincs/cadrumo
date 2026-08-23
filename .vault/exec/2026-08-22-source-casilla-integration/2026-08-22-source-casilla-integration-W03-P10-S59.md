---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f5cf7dd8c1b38379f8705996ec3fe1bef638c1039e75c16d83f1d37eb9261ab2'
step_id: 'S59'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
---

# decide grain, precedence, absence semantics, rounding, and override policy

## Scope

- `.vault/adr/2026-08-23-amortization-casilla-mapping-adr.md`

## Description

- Require per-asset legal validation before activity aggregation.
- Partition output by material and intangible legal classification.
- Fail closed on missing, unreadable, incomplete, duplicate, or unsupported schedules.
- Refuse transaction-source and caller collisions instead of applying precedence.
- Restrict automation to grounded 2025 rules and elections.

## Outcome

The accepted ADR defines exclusive source ownership, refusal semantics, and the validation boundary for activity amortization. Unsupported treatments remain visibly manual or blocked rather than approximated.

## Notes

Exact rounding follows the registry-grounded monetary output contract during implementation; no independent rounding authority is introduced here.
