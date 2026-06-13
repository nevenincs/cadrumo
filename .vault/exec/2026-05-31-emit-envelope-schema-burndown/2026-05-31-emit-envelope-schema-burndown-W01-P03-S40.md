---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S40
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W01.P03 — ledger import/export/track/review verbs

## Outcome

Added 4 import/export/track/review `OutputSchema` subclasses: `LedgerExportResult`, `LedgerImportResult`, `LedgerTrackResult`, `LedgerReviewResult`. `LedgerImportResult` carries nested `LedgerImportValidationPayload` and `LedgerImportSourcePayload` sub-models. `LedgerReviewResult` uses fully-optional fields to cover three discriminated paths (empty result, single-row detail, multi-row list). `LedgerExportResultSchema` and `LedgerImportResultSchema` aliases avoid name collisions with identically-named domain models.

## Files changed

- `src/aeat/entrypoints/cli/_ledger_payloads.py` — 4 import/export schemas added
- `src/aeat/entrypoints/cli/_ledger.py` — 4 bare emit sites migrated

## Gate

109 ledger CLI tests + conformance gate passed.
