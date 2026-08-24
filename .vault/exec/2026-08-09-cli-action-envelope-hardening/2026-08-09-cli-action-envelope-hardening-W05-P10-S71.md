---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:018047d65b1aeb918752528012a15f213c03e060c81ad600d997ef4b5922de0e'
step_id: 'S71'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate aggregation recovery producers to canonical typed conditions

## Scope

- `src/cadrumo/application/aggregation/_errors.py`
- `src/cadrumo/application/aggregation/_service.py`
- `src/cadrumo/application/aggregation/_modelo_bindings.py`
- `src/cadrumo/application/aggregation/tests`

## Description

- Replace bespoke aggregation terminal-verdict storage with the standard mixin transport.
- Census the complete aggregation recovery attachment population.
- Prove exact condition, fact-expression, provenance, outcome, and canonical-helper authority for all five carriers.
- Assert the full terminal contract at runtime for unsupported modelo, both invoice-ledger completeness paths, and missing retenciones observations.

## Outcome

The only aggregation recovery producers are five canonical attachments across three conditions: unsupported modelo twice, invoice-ledger completeness twice, and missing retenciones observations once. `AggregationError` uses `TerminalPreconditionErrorMixin`; no manual verdict storage or direct verdict/evidence construction remains.

The exact totality gate and runtime contracts pass six tests. Scoped Ruff and diff checks pass. Independent review confirmed the three broader aggregation reds belong to separate composite-source provenance and invoice-screening behavior, not S71 transport or verdict semantics.

## Notes

- Two M720 tests remain red because successful aggregation results lose provenance; no aggregation refusal is constructed or reached.
- One source-mesh test disagrees with the pre-existing invoice-completeness predicate, while the refusal’s terminal contract is independently proven here.
