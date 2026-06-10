---
generated: true
tags:
  - '#index'
  - '#live-justificante-reconcile'
date: '2026-06-10'
related:
  - '[[2026-06-10-live-justificante-reconcile-P01-S01]]'
  - '[[2026-06-10-live-justificante-reconcile-P01-S02]]'
  - '[[2026-06-10-live-justificante-reconcile-P01-S03]]'
  - '[[2026-06-10-live-justificante-reconcile-P01-summary]]'
  - '[[2026-06-10-live-justificante-reconcile-P02-S04]]'
  - '[[2026-06-10-live-justificante-reconcile-P02-S05]]'
  - '[[2026-06-10-live-justificante-reconcile-P02-S06]]'
  - '[[2026-06-10-live-justificante-reconcile-P02-summary]]'
  - '[[2026-06-10-live-justificante-reconcile-adr]]'
  - '[[2026-06-10-live-justificante-reconcile-plan]]'
  - '[[2026-06-10-live-justificante-reconcile-research]]'
---

# `live-justificante-reconcile` feature index

Auto-generated index of all documents tagged with `#live-justificante-reconcile`.

## Documents

### adr

- `2026-06-10-live-justificante-reconcile-adr` - `live-justificante-reconcile` adr: `live-sourced justificante reconciliation bridge` | (**status:** `accepted`)

### exec

- `2026-06-10-live-justificante-reconcile-P01-S01` - Register the live justificante-capture secure-object namespace at FINANCIAL sensitivity and re-export it, verified by the namespace registry test
- `2026-06-10-live-justificante-reconcile-P01-S02` - Author the JustificanteCaptureSnapshot payload (modelo via core Modelo enum, filing_year, period, expediente_id, csv, pdf_sha256, pdf_bytes, official source_kind, lifecycle), object-key, content-addressed id, repository and SnapshotService hooks mirroring Borrador100.
- `2026-06-10-live-justificante-reconcile-P01-S03` - Prove the persistence boundary with a strict secure-storage roundtrip (every defaultable field non-default), a supersession lifecycle test, and an anti-tautology mutate-on-disk proof.
- `2026-06-10-live-justificante-reconcile-P01-summary` - `live-justificante-reconcile` `P01` summary
- `2026-06-10-live-justificante-reconcile-P02-S04` - Add the require_live_read-gated async capture_justificante_snapshot orchestrator (period-aware expediente resolution, capture_justificante, service.capture) and promote it plus the service to the package top-level re-exports.
- `2026-06-10-live-justificante-reconcile-P02-S05` - Prove period disambiguation (1T vs 2T resolve to distinct expedientes, never the wrong quarter) and orchestrator wiring offline with a real service and a seam-injected session.
- `2026-06-10-live-justificante-reconcile-P02-S06` - Add a live end-to-end capture test gated by AEAT_LIVE_TESTS_ENABLED that pulls and persists a real justificante, env-driven and never xfail or skip-marker
- `2026-06-10-live-justificante-reconcile-P02-summary` - `live-justificante-reconcile` `P02` summary

### plan

- `2026-06-10-live-justificante-reconcile-plan` - `live-justificante-reconcile` `live-sourced justificante reconciliation` plan

### research

- `2026-06-10-live-justificante-reconcile-research` - `live-justificante-reconcile` research: `live-sourced justificante reconciliation`
