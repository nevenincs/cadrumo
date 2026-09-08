---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:bdb104e01dbfaf746c29d6fc5eb93d91a3e99224cf4dd5fbb4c168e546efedc6'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S202]]"
---

# `reachability-burndown` audit: `S202 invoice column census withdrawal review`

## Scope

Independent bounded review of W05.P12.S202: removal of the test-only invoice allowed/optional aggregates, model-derived FieldRole coverage, retained runtime parser authorities, cadence guidance, and Step Record evidence.

## Findings

No findings.

The removed `BULK_INVOICE_IMPORT_ALLOWED_COLUMNS` aggregate was consumed only by the cross-importer coverage test; its optional complement became dead with it. The replacement `frozenset(BulkInvoiceImportRow.model_fields)` derives the accepted population directly from the strict executable row schema, so any field addition or removal changes coverage without a mirrored census edit. The test remains discriminating because FieldRole declarations are a separate authority compared against that derived schema, not generated from the same role mapping.

`BULK_INVOICE_IMPORT_REQUIRED_COLUMNS` remains live in runtime missing-column refusal. Classification-import allowed columns remain separately runtime-owned and are not conflated with invoice schema completeness. The unchanged aggregate finding count is honestly recorded as concurrent drift while exact residue proves both removed names absent.

The Step Record names exact paths and exact Ruff, focused 30-test, residue, metastate, and live reachability commands. The cadence addition correctly generalizes derivation from executable schemas without introducing a maintained identity list.

## Recommendations

Approve W05.P12.S202. No correction is required.
