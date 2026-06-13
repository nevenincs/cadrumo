---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-06-calculation-truth-registry-exec]]'
---



# `calculation-truth-registry` Code Review


RENTA-SCENARIO-001 | LOW | Scenario runner must bind declared revision
The initial scenario runner accepted a `revision` field but selected the registry
snapshot only from modelo, filing year, and period. That made the scenario
record less strict than its schema suggested and could hide year-over-year Renta
drift if a scenario carried the wrong revision label. Closed in this slice by
passing the declared revision to snapshot selection and adding a negative
scenario that fails when a 2025 scenario claims revision `2024`.

RENTA-SCENARIO-002 | INFO | No open findings after focused review
Reviewed the local scenario harness, exported API surface, Renta scenario tests,
execution record, plan update, and ADR update. The harness now checks numeric
values, operand refs, legal refs, source refs, and declared revision selection
through real registry loading and snapshot calculation.

RENTA-SCENARIO-003 | INFO | Scenario matrix expanded beyond economic activities
Reviewed the added real-estate capital and final-settlement scenarios. They
exercise existing registry-backed formulas through the scenario harness and add
trace/evidence assertions for capital-inmobiliario rollups, rental withholding,
cuota diferencial, and resultado de la declaracion. No open finding.

RENTA-ORACLE-001 | INFO | Renta WEB Open adapter no longer hard-fails verification
Reviewed the Renta WEB Open oracle update. The adapter now preflights planned
operations, returns `blocked` on guard refusal, returns `unverifiable` when no
live driver is configured, and supports deterministic local replay comparisons
that return `match`, `mismatch`, or `unverifiable` without touching AEAT.

RENTA-LIVE-001 | INFO | Renta WEB Open baseline live calculation checker passes
Reviewed the live checker path. It opens the anonymous AEAT Renta WEB Open 2025
simulator, fills a valid synthetic personal profile, scrapes summary output
fields, and compares them through `ParityResult`. The opt-in `live_read` test
matched resultado de la declaracion, minimo personal/familiar estatal y
autonomico, and cuota diferencial against AEAT on 2026-05-06.
