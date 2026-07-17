---
tags:
  - '#exec'
  - '#iva-compensation-override-cli'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-06-19-iva-compensation-override-cli-plan]]"
---

# Emit a MODELO_IVA_WALLET override audit event carrying reason and evidence_locator provenance through the single BucketEventHistoryRepository

## Scope

- `src/aeat/application/modelo/_iva_wallet_seed.py`

## Description

- Emit a `MODELO_IVA_WALLET_OVERRIDE_RECORDED` audit event when an override is recorded.
- Carry the reason and evidence-locator provenance plus taxpayer NIF, filing year, period, and amount in the event payload.
- Route the emission through the single `BucketEventHistoryRepository` append path with a derived, clock-stamped event id.

## Outcome

- Each recorded override appends exactly one typed bucket event through the shared single-writer history repository, alongside the reconciliation's own decision persistence.
- Provenance (reason, evidence locator) is auditable from the event payload.
- Verified green by the override behaviour and CLI conformance suites.

## Notes

- Delegates to the existing single bucket-event emission path rather than opening a parallel write, per the composition-service single-writer discipline.
- The emitter implementation was present at HEAD; this Step verified it against real gates and closed it with an execution record.
