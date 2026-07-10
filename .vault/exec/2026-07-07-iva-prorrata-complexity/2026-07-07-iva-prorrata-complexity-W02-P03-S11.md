---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-08'
step_id: 'S11'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Add the typed input_classification axis (core InputClassification) to the ledger transaction, operator-declared for especial buckets, with roundtrip + anti-tautology proof

## Scope

- `src/aeat/domain/transactions/_models.py`

## Description

- Add the typed `input_classification` axis (the existing core `InputClassification` StrEnum: EXCLUSIVELY_DEDUCTIBLE / EXCLUSIVELY_NON_DEDUCTIBLE / COMMON) to the ledger `Transaction`, operator-declared and meaningful for buckets under prorrata especial.
- Coerce the field from its JSON string form and document its art-106 per-input-use semantics on the model.
- Add a strict JSON save/load/equality roundtrip with the classification set non-default, plus a load-time refusal of a non-member value.

## Outcome

- Modified files: `src/aeat/domain/transactions/_models.py`, `src/aeat/domain/transactions/tests/test_models.py`.
- 7 focused transaction tests pass (input_classification roundtrip/refusal + the existing art-104 and roundtrip regressions); ruff / ruff-format / ty clean.
- Committed atomically with this exec record and the plan step check.

## Notes

- Consumes the existing `InputClassification` enum from `domain.iva` (the 2026-05-12 substrate); no new classification type authored, per the especial ADR's "consume the substrate" constraint.
- Unlike the art-104.Tres tag, all three InputClassification members are legitimate operator declarations (regla 1a/2a/3a), so no operator-vs-auto restriction validator is needed - the field is a straight per-input use declaration.
