---
tags:
  - '#exec'
  - '#determinism-replay-residual'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:d8edffd6cc323e12792a6580cf579954eeafaea3f2a6d820af33bc1aa90d12e8'
step_id: 'S02'
related:
  - "[[2026-07-01-determinism-replay-residual-plan]]"
---

# Content-address evidence_id and invoice_id via a clock-free content digest over identifying fields with genuine-duplicate disambiguation

## Scope

- `add roundtrip + anti-tautology proofs`
- `add a ledger-evidence --format json golden scenario under frozen_clock with injected profile_id`
- `adding a residual mask entry only if an opaque single-command leaf remains.`
- `src/aeat/application/ledger/_evidence.py`
- `src/aeat/application/ledger/_business_operation_invoice.py`
- `src/aeat/core/observability/_golden.py`

## Description

- Add `derive_purchase_invoice_evidence_id` in `_evidence.py`: a SHA-256 content digest (truncated to 16 hex, the prior surrogate's width) over the record's identifying fields (bucket, source sha256, media kind, supplier, invoice number/date, taxable base, iva rate/amount, notes) plus `created_at` and a `disambiguator` ordinal, mirroring `derive_transaction_id`.
- Add `derive_business_operation_invoice_id` in `_business_operation_invoice.py` with the same shape over the invoice's identifying fields (counterparty, invoice number/date, currency, amounts, intracom fields) plus `created_at` + `disambiguator`.
- Wire both mint sites: load the catalogue first, derive the id, and increment the `disambiguator` on the rare digest collision so two genuinely-distinct records minted at the same coarse-clock instant keep distinct ids (the genuine-duplicate case the ledger preserves). Drop the `uuid4().hex[:16]` surrogate and the now-unused `import uuid` from both modules.
- Normalise `country_code` to the stored (upper) form before deriving the invoice id so the id derives from the persisted value.
- Add `test_content_addressed_ids.py`: for both ids, prove the minted id equals the pure `derive_*_id` digest of the record's own fields, the record round-trips through the real encrypted `SecureObjectRepository` with the id surviving a fresh-repository reload, the id is content-derived not constant (anti-tautology), and two genuine duplicates minted at the same frozen instant stay distinct via the disambiguator.

## Outcome

- Content-addressed ids are deterministic under `frozen_clock`, so the ledger-evidence/invoice `--format json` envelopes carry no residual opaque leaf: `GOLDEN_MASK_FIELDS` is UNCHANGED and the parent anti-tautology proof (`test_mask_equals_the_residual_diff_under_frozen_clock`) still resolves to exactly `{snapshot_id, run_id}`. No mask entry was added (the ADR's residual-fallback was not needed).
- New tests pass (6/6); the full `src/aeat/application/ledger/tests` + `test_golden.py` run is green (372 passed); CLI business-invoice verbs and the aggregation renta-ledger/filing-snapshot id consumers are green (35 passed). `collect-only src/aeat/application/ledger` clean (357); ruff clean.
- No back-migration: the id shape changes on write only; there is no released data to coerce (`no-legacy-compatibility`).

## Notes

- The ledger-evidence `--format json` golden scenario paired with this decision is realized by ENROLLING `ledger.evidence.add` in the D4 determinism-conformance axis (`test_determinism_conformance.py`), per the ADR Consequences ("content-addressed ledger ids let the ledger-evidence ... scenarios enrol in the decision-4 determinism-coverage axis") — not a duplicate standalone test. The axis captures the evidence-add envelope across two fresh-bucket runs (same synthetic PDF, same fields, same injected profile identity, same frozen instant) and asserts byte-identical with ZERO residual differing fields, so the content-addressed evidence_id needs no mask and the parent anti-tautology proof stays exactly {snapshot_id, run_id} (re-run green). Distinct from the axis's ledger-add retried-no-op case.
- Integration lesson: a storage write under `frozen_clock` resets the bucket session's idle deadline to the frozen instant, so every storage op in a frozen scenario must stay under one `frozen_clock` block (as replay freezes the whole run); a later real-clock read otherwise sees the session expired. The tests are structured accordingly. This also constrains the P04 ledger-add-no-op case.
