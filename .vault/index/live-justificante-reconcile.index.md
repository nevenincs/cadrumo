---
generated: true
tags:
  - '#index'
  - '#live-justificante-reconcile'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:fc856216ee3dd245603eef105f0d5c2b754d0c13bc22004649ecfaf7862a3770'
related:
  - '[[2026-06-10-live-justificante-reconcile-P01-S01]]'
  - '[[2026-06-10-live-justificante-reconcile-P01-S02]]'
  - '[[2026-06-10-live-justificante-reconcile-P01-S03]]'
  - '[[2026-06-10-live-justificante-reconcile-P01-summary]]'
  - '[[2026-06-10-live-justificante-reconcile-P02-S04]]'
  - '[[2026-06-10-live-justificante-reconcile-P02-S05]]'
  - '[[2026-06-10-live-justificante-reconcile-P02-S06]]'
  - '[[2026-06-10-live-justificante-reconcile-P02-summary]]'
  - '[[2026-06-10-live-justificante-reconcile-P03-S07]]'
  - '[[2026-06-10-live-justificante-reconcile-P03-S08]]'
  - '[[2026-06-10-live-justificante-reconcile-P03-summary]]'
  - '[[2026-06-10-live-justificante-reconcile-P04-S09]]'
  - '[[2026-06-10-live-justificante-reconcile-P04-S10]]'
  - '[[2026-06-10-live-justificante-reconcile-P04-summary]]'
  - '[[2026-06-10-live-justificante-reconcile-P05-S11]]'
  - '[[2026-06-10-live-justificante-reconcile-P05-S12]]'
  - '[[2026-06-10-live-justificante-reconcile-P05-S13]]'
  - '[[2026-06-10-live-justificante-reconcile-P05-S14]]'
  - '[[2026-06-10-live-justificante-reconcile-P05-summary]]'
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
- `2026-06-10-live-justificante-reconcile-P03-S07` - Stamp the captured justificante as official evidence (aeat_sede_live_capture observation plus ExternalEvidence on the filing record) reusing the import_external_filing_evidence single-writer pattern.
- `2026-06-10-live-justificante-reconcile-P03-S08` - Prove a dependent period whose only upstream evidence is the live capture no longer raises MISSING_JUSTIFICANTE_VERIFICATION, and that a non-official kind still would.
- `2026-06-10-live-justificante-reconcile-P03-summary` - `live-justificante-reconcile` `P03` summary
- `2026-06-10-live-justificante-reconcile-P04-S09` - Add the reconcile-from-persisted seam that materialises stored pdf_bytes to a transient readable path, runs the unchanged local modelo_reconcile, and preserves the parser path-redaction behaviour.
- `2026-06-10-live-justificante-reconcile-P04-S10` - Prove reconcile against a persisted live capture yields the expected verdict and that no caller-controlled path leaks into error messages.
- `2026-06-10-live-justificante-reconcile-P04-summary` - `live-justificante-reconcile` `P04` summary
- `2026-06-10-live-justificante-reconcile-P05-S11` - Add the aeat app live justificante capture/list/view verbs mirroring the expedientes CLI, with typed result payloads.
- `2026-06-10-live-justificante-reconcile-P05-S12` - Register the justificante sub-app on the live read command group, verified by the live read subgroups test
- `2026-06-10-live-justificante-reconcile-P05-S13` - Add the cli.app.live.justificante locale keys across all four catalogues through the aeat.locales CLI, verified by parity and translation-honesty gates
- `2026-06-10-live-justificante-reconcile-P05-S14` - Regenerate the API reference stubs for the new modules via the apidocs CLI and gate documented-command conformance plus scaffold --check.
- `2026-06-10-live-justificante-reconcile-P05-summary` - `live-justificante-reconcile` `P05` summary

### plan

- `2026-06-10-live-justificante-reconcile-plan` - `live-justificante-reconcile` `live-sourced justificante reconciliation` plan

### research

- `2026-06-10-live-justificante-reconcile-research` - `live-justificante-reconcile` research: `live-sourced justificante reconciliation`
