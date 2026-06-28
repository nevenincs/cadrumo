---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S41'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C3 Extract a single-catalogue secure repository base and route the four substitutable catalogue repos through it

## Scope

- `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`

## Description

- Read the full `load`/`save` of the four candidate catalogue repositories
  (`buckets/_event_repository`, `invoices/_repository`,
  `modelos/_filing_repository`, `modelos/_verification_repository`) plus
  `modelos/_calculation_repository`, applying the substitutability pre-filter.

## Outcome

**Constraint-divergent — NOT actioned (no leaky base forced).** A shared
`SingleCatalogueRepository` base / decode kernel is not cleanly extractable:
the envelope-validation error handling is bespoke per repo, and a forced base
would need ~6 hooks to reproduce each repo's behaviour — the leaky-abstraction
the pre-filter exists to prevent (the agent's "4 substitutable" rating was the
lexical-cluster optimism the close-read reverses). The one genuinely-common
shape (the `_objects.load` integrity-except wrapper) was already consolidated by
B1 (`raise_catalogue_integrity_error`).

Divergences found on close read:

- **Error class + context shape per repo.** calc/verification raise their typed
  `*PersistenceError` with rich `{reason: classification_mismatch,
  expected_classification, actual_classification}` context and a detailed
  `_LOGGER.error(extra=...)`; invoices raises a **bare** `ClassificationError`
  with a simple message and no context; event wraps with
  `{namespace, object_key, ...}` context. These are load-bearing per-repo
  diagnostics, not noise.
- **Empty-on-None** returns a different catalogue type per repo
  (`InvoiceCatalogue` / `ModeloRecordCatalogue` / `VerificationReportCatalogue` /
  `BucketEventHistoryCatalogue`).
- **Save** diverges: invoices/calc use `_objects.save(...)`; event uses
  `to_secure_object_write` -> `save_many(...)`.

The only byte-identical fragment is the one-line
`Envelope[T].model_validate_json(record.payload.decode("utf-8"))` decode — a
trivial stdlib-shaped idiom (F4-class) whose extraction would dedupe one line at
the cost of a generic indirection; excluded.

## Notes

Harmonising the four repos onto one error contract (so a clean base becomes
possible) would change error types/messages/context across four FINANCIAL
persistence boundaries — a redesign beyond dedup scope, with no evidence the
per-repo diagnostics are accidental. Recorded as the disciplined pre-filter
verdict; revisit only via an explicit error-contract-unification ADR. C4 folds
into this finding (its only shared logic was the catalogue-record unwrap a base
would have owned).
