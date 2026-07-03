---
tags:
  - '#exec'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-29'
step_id: 'S07'
related:
  - "[[2026-06-14-legal-grounding-centralization-plan]]"
---

# F2-final: decide prorrata subsystem fate — enroll as registry-declared aggregation source on 303/390 casillas OR delete the dormant subsystem per no-legacy-compatibility

## Scope

- `src/aeat/domain/iva/_prorrata.py`
- `src/aeat/application/aggregation/_prorrata.py`
- `src/aeat/application/aggregation/__init__.py`

## Description

- Re-confirm at HEAD that the exported application prorrata aggregation wrapper
  (`aggregate_prorrata_inputs`, `aggregate_provisional_prorrata`,
  `aggregate_definitiva_prorrata`, `ProrrataAggregation`, `IvaOperation`, and
  `IvaOperationKind`) has no non-test caller and no live `BindingSourceKind`
  enrollment.
- Delete the exported dormant application aggregation surface instead of retaining
  unused capacity. Keep the active `domain.iva._prorrata` substrate because IVA ledger
  aggregation validates `prorrata_reference` values through it.

## Outcome

2026-06-29 supersession: the earlier deferral decision is replaced by deletion of the
exported application wrapper. `application.aggregation` no longer imports or exports
the prorrata wrapper names, `src/aeat/application/aggregation/_prorrata.py` and its
application-level test file are deleted, and the terminology relevance artifact no
longer points at `api/aeat.application.aggregation._prorrata.html`.

The retained surface is narrower: `domain.iva._prorrata` remains the legal substrate for
LIVA art. 9.1.c, 102, and 103 percentage/reference semantics, and
`application.aggregation._iva_ledger` uses `validate_prorrata_reference` only to validate
ledger-attached prorrata reference ids. That path does not own Modelo casilla routing and
does not introduce a dormant source resolver.

## Notes

Verification for the supersession is recorded in
`[[2026-06-14-legal-grounding-centralization-audit]]` V33. Focused checks passed for IVA
prorrata/IVA ledger behaviour, package import smoke, terminology target resolution, Sphinx
docs build, and the RAG reindex/search pass.
