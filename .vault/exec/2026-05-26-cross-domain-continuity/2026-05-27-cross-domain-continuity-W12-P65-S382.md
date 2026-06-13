---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S382
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
---

# `cross-domain-continuity` `W12.P65.S382`

Lock the source_jurisdiction axis at the encrypted persistence boundary and propagate to the review and export read projections. No DDL change, no migration script, no envelope schema-version bump — the catalogue is an opaque JSON envelope and the strict pydantic `Transaction` model from S381 IS the persistence schema.

Commit: `40f3837b8`

- Modified: `src/aeat/application/ledger/_models.py`
- Modified: `src/aeat/domain/transactions/test_repository_roundtrip.py`

## Description

Propagated the field to two parallel application-layer projections:

- `LedgerTransactionReviewPayload` — same `str | None = None` field plus the 2-char alpha-uppercase validator (matches the S381 LedgerTransactionPayload binding).
- `LedgerExportRow` — `str = ""` empty-string default, matching the existing flat-string export-row convention (cf. `business_pct: str = ""`). No validator on the export row; the field is a serialised projection of an already-validated upstream value.

Added two anti-tautology tests against the real encrypted catalogue repository (`TransactionCatalogueRepository`, real `isolated_runtime_profile`, real `SecureObjectRepository`):

- `test_transaction_catalogue_preserves_source_jurisdiction_through_encrypted_storage` — save Transaction with `source_jurisdiction="ES"`, open a fresh repository to load, assert strict catalogue equality plus restored `"ES"`. Exercises the FINANCIAL-classification envelope through the secure-object adapter end-to-end.
- `test_transaction_catalogue_grandfathers_missing_source_jurisdiction_key` — save with `"ES"`, surgically delete the `source_jurisdiction` key from the persisted JSON envelope via the underlying secure-object repository, reload, assert `loaded_txn.source_jurisdiction is None` AND `loaded != original` (strict-inequality witness). The strict-inequality assertion is the kill-the-mutant target: it would fail if the field were silently restored to the default at load time without entering pydantic equality, locking the field's identity contribution.

## Verification

- Both roundtrip tests pass against the real encrypted-SQL adapter under `isolated_runtime_profile`.
- `_TX_CATALOGUE_VERSION` stays at 1 — additive JSON-compatible field, pre-S381 envelopes deserialise cleanly with the `None` default. Same shape as how `fx_rate` and `value_in_eur` were added under W05.P23.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: review payload validator added; export row uses empty-string flat default per convention.
- G3 user messages via tr(): N/A.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: pattern-mirror of S381 validator on the parallel projection; export-row matches the flat-default convention.
- G6 no tautological tests: anti-tautology proof surgically mutates the persisted envelope to force the grandfather branch and inequality assertion.

## References

- ADR: source-jurisdiction-axis-adr (Constraints — envelope additivity, grandfather contract)
- Sibling Steps: S381 (model field), S383 (write-side wiring), S385 (aggregation provenance).
- Sibling commits in this Step: none — single-commit leaf.
- Surface: `TransactionCatalogueRepository` at `src/aeat/domain/transactions/_repository.py`; roundtrip tests at `test_repository_roundtrip.py`.
