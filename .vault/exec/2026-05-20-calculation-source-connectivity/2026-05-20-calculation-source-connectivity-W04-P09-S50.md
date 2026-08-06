---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:077cc36c3790e050b0e428c5018c89b508fee53905d5f607ee6208ff461f57c8'
step_id: 'S50'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Persist source refs and fingerprints on calculation revisions

## Scope

- `src/aeat/domain/modelos/_calculation.py`

## Description

- Add the compact `CalculationSourceRef` domain model (source_kind, typed binding_source, source_ref, fingerprint) to the calculation-revision module; the plan scoped file `_calculation.py` is the current `_calculation_revision.py`.
- Add an additive `source_provenance` tuple field on `CalculationRevision`, defaulting to empty for backward compatibility.
- Keep `source_provenance` OUT of `derive_calculation_revision_id`, mirroring `ledger_filing_snapshot` / `ledger_filing_evidence`, so the content-addressed id is unaffected.
- Deliberately omit `legal_refs` / `source_refs` from the ref model; per-casilla grounding stays on the revision observations.
- Export `CalculationSourceRef` from the calculation-revision `__all__` and the `domain.modelos` package facade.
- Map application `CalculationSourceProvenance` to the domain `CalculationSourceRef` at the persist boundary and thread `source_provenance` through `persist_calculation_revision`, `calculate_modelo_revision`, and the bucket-aggregation calculate path.

## Outcome

Every ledger/invoice/carry resolver that contributes to a calculation now leaves a persisted resolver-to-source-object-to-fingerprint trace on the revision. Verified the id is invariant to `source_provenance` (identical ids with and without the field) and that the field survives the encrypted repository roundtrip.

## Notes

The domain model imports `BindingSourceKind` from `core.aggregation` (domain-to-core is legal); it never imports the application-layer provenance model. The strict `min_length` constraints on `source_kind` / `source_ref` are what the S53 anti-tautology proof bites on.
