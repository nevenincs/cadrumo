---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S381
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
---

# `cross-domain-continuity` `W12.P65.S381`

First leaf of the source_jurisdiction axis: add the ISO 3166-1 alpha-2 field to the domain `Transaction` model and to the canonical `LedgerTransactionPayload` read projection, with a strict two-character alpha-uppercase validator and a grandfather-friendly `None` default.

Commit: `b7c571297`

- Modified: `src/aeat/domain/transactions/_models.py`
- Modified: `src/aeat/application/ledger/_models.py`
- Modified: `src/aeat/domain/transactions/test_models.py`

## Description

Added `source_jurisdiction: str | None = None` to the strict-frozen `Transaction` model after the `value_in_eur` field, with a `_validate_source_jurisdiction` field-validator that:

- Returns `None` for the absent / grandfather case.
- Trims whitespace, then rejects values that are not exactly two ASCII-alpha uppercase characters.
- Returns the canonical value otherwise.

Errors surface through `TransactionValidationError` so the existing domain-error funnel applies.

Mirrored the field and validator onto `LedgerTransactionPayload` (the canonical CLI/API read projection). The application-layer copy raises `ValueError` (pydantic-standard at the application boundary), while the domain layer raises the typed domain error, matching the existing pattern across these models.

Extended the `Transaction` docstring with the new attribute entry, explaining the regulatory anchors (LIRPF Art. 8 default for residents, TRLIRNR Art. 25 IRNR scope filter, LIRPF Art. 93 Beckham segregation) and the grandfather behaviour for pre-axis catalogues.

## Verification

Four anti-tautology tests appended to `test_models.py`:

- `test_source_jurisdiction_roundtrips_es_through_json` — save `"ES"`, JSON-roundtrip via `model_validate_json(model_dump_json())`, assert strict pydantic equality plus restored value.
- `test_source_jurisdiction_preserves_none_grandfather_state` — omit field, roundtrip, assert `None` preserved. Locks the grandfather contract at the model layer.
- `test_source_jurisdiction_rejects_non_iso_alpha2_codes` — validator rejects `"INVALID"`, `"es"` (lower), `"E1"` (digit), `"E"` (length 1), `"ESP"` (length 3), `"  "` (whitespace-only).
- `test_source_jurisdiction_normalises_surrounding_whitespace` — `" FR "` normalises to `"FR"`.

Each test has a distinct kill-the-mutant target: roundtrip identity, grandfather preservation, malformed rejection, whitespace normalisation.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: new strict optional field with intrinsic validator on both Transaction and LedgerTransactionPayload.
- G3 user messages via tr(): N/A; validator messages are dev-error shape, wrapped operator-facing at S383's CLI surface.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: single validator pattern repeated across two strict-frozen classes; pattern-mirror not abstraction.
- G6 no tautological tests: each assertion derives from the validator contract, not from re-running the validator.

## References

- ADR: source-jurisdiction-axis-adr
- Sibling Steps: S382 (encrypted-envelope roundtrip), S383 (write-side wiring), S384 (profile-conditional resolver), S385 (aggregation provenance), S386 (ADR consolidation).
- Sibling commits in this Step: none — single-commit leaf.
- Surface: `Transaction.source_jurisdiction` at `src/aeat/domain/transactions/_models.py:796`; `LedgerTransactionPayload.source_jurisdiction` at `src/aeat/application/ledger/_models.py:273`.
