---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S385
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
---

# `cross-domain-continuity` `W12.P65.S385`

Thread the per-row source_jurisdiction provenance from each ledger transaction onto the `RentaIncomeObservation` produced by the M130 / M100 actividad-económica aggregation. Provenance pass-through only — NO gating at this surface, per LIRPF Art. 8 universal-base presumption.

Commit: `0a153a83c` (plan-Step S385, prior descope labelled S385a in the chain log)

- Modified: `src/aeat/application/aggregation/_renta_income_ledger.py`
- Modified: `src/aeat/application/aggregation/test_renta_income_aggregation.py`

## Description

The original S385 spec called for per-row gating at IRNR M210 and Beckham M151 aggregation surfaces. Grounding sweep confirmed those engines do not yet exist (M210 is still at the Path-B refusal stub from #196; the M151 engine is at the Path-B stub from #161). The Step was therefore descoped to the M130/M100 surface that DOES exist, with the deferred per-row gating tracked as task #62 (S385b) — blocked by the future IRNR full engine and Beckham M151 engine landing.

The implementation is intentionally narrow:

- `RentaIncomeObservation` gains `source_jurisdiction: str | None = None` after `filing_date`. The model docstring is extended to explain the LIRPF Art. 8 universal-base presumption and the provenance role at this surface (no filtering).
- `_classify_income_transaction` threads `transaction.source_jurisdiction` into the eligible-row return site, alongside the existing per-row fields.

No filter is applied. Resident-IRPF aggregation accepts foreign-source rows into the casilla sum, consistent with the worldwide-income base. The field exists so downstream consumers (the future IRNR M210 engine, the future Beckham M151 engine, the audit surface) can read the jurisdiction without retrofitting the read-side.

## Verification

Two anti-tautology tests appended to `test_renta_income_aggregation.py`:

- `test_renta_income_observation_preserves_es_source_jurisdiction` — single ES actividad row through, assert the resulting observation carries `source_jurisdiction == "ES"`. Single-row provenance witness; kills the classifier-strip regression.
- `test_renta_income_aggregation_mixes_es_and_foreign_source` — ES + FR actividad rows through Q1 2024, assert (a) both observations present, (b) casilla 01 sums both amounts (LIRPF Art. 8), (c) each observation preserves its own declared jurisdiction (distinct-preservation). Universal-base + distinct-preservation witness; kills the "filter foreign source for cleanliness" mutation.

Each test docstring cites LIRPF Art. 8 explicitly and references the future IRNR/Beckham per-row gating consumers. The test fixture is a new helper `_actividad_transaction_with_source` built via `Transaction.model_validate` directly to avoid expanding the shared `_actividad_transaction` signature.

Smoke result: 2 passed in 1.33s.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: `RentaIncomeObservation` field is strict optional with no validator (the originating Transaction's regex validator from S381 is the typo gate; no untyped boundary introduced).
- G3 user messages via tr(): N/A; aggregation-internal.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: new tests build via `Transaction.model_validate`, no fixture-signature growth.
- G6 no tautological tests: expected outcomes derive from Art. 8 universal-base, not from re-running the classifier. The mixed-source test would fail loudly against any future "drop foreign source" mutation.

## References

- ADR: source-jurisdiction-axis-adr (Implementation §S385, Rationale on aggregation-surface design)
- Sibling Steps: S381 (model field), S382 (encrypted roundtrip), S383 (CLI flag), S384 (profile-conditional resolver), S386 (ADR).
- Sibling commits in this Step: none — single-commit leaf.
- Deferred: S385b per-row gating at IRNR M210 and Beckham M151 engines (task #62; blocked by IRNR full engine + M151 engine authoring).
- Surface: `RentaIncomeObservation.source_jurisdiction` at `src/aeat/application/aggregation/_renta_income_ledger.py`; classifier wire at `_classify_income_transaction`; tests at `test_renta_income_aggregation.py` end.
