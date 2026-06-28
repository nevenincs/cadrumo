---
tags:
  - '#exec'
  - '#core-authority'
step_id: S89
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W10.P27.S89 - audit: ReconciliationStatus vs SubmissionStatus divergence

## Outcome

Audit completed. ReconciliationStatus and SubmissionStatus are semantically distinct
and serve different domain concerns. Consolidation rationale: DO NOT MERGE.

- `ReconciliationStatus` (application/filing/reconciliation/_schema.py:34): Three-outcome
  verdict of a ModeloDraft vs Justificante comparison — COINCIDE, DIVERGENTE, NOT_YET_FOUND.
  Operator-observable result of the reconciliation pipeline.

- `SubmissionStatus` (domain/submission/_models.py:22): Lifecycle state of a
  ModeloPresentado — PENDIENTE_DE_PRESENTAR, EN_TRAMITACION, PRESENTADA, ACEPTADA,
  RECHAZADA, FALLIDA. Values mirror AEAT Sede labels per ADR A7.2.

Zero semantic overlap between these two enums. The tracker (MERGE-004) claimed "50%
overlap" which appears to be a confusion with ModeloDraftStatus vs SubmissionStatus
(PAIR E-04 in the semantic audit), which share PRESENTADA/ACEPTADA/RECHAZADA. The
audit correctly identifies that divergence is intentional.

Explicit divergence: filing reconciliation verdict (COINCIDE/DIVERGENTE/NOT_YET_FOUND)
vs submission lifecycle (PENDIENTE.../EN_TRAMITACION/PRESENTADA/ACEPTADA/RECHAZADA/FALLIDA)
serve fundamentally different business concerns and must remain separate.

## Files touched

None — audit step only.

## Verification

N/A (audit step, no code changes).
