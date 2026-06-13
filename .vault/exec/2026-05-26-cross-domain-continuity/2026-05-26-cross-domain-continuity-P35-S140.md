---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
step_id: W08.P35.S140
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---


# cross-domain-continuity W08.P35.S140 — Haiku discovery sweep: remaining f-string error raises in application layer

## Outcome

Sweep of `src/aeat/application/` (excluding `_actions.py` and test files) found
**120 remaining hardcoded f-string error raises** across **43 files**.

## Affected files

```
src/aeat/application/aggregation/_counterpart.py
src/aeat/application/aggregation/_foreign_assets.py
src/aeat/application/aggregation/_retenciones.py
src/aeat/application/aggregation/_service.py
src/aeat/application/auth/_sessions.py
src/aeat/application/calculations/_binding_prefill.py
src/aeat/application/calculations/_iva_compensation_history.py
src/aeat/application/calculations/_observations_repository.py
src/aeat/application/calculations/_row_set_assembly.py
src/aeat/application/export/_tabular.py
src/aeat/application/filing/__init__.py
src/aeat/application/filing/_complementaria.py
src/aeat/application/filing/_export.py
src/aeat/application/filing/_import.py
src/aeat/application/filing/_review.py
src/aeat/application/filing/_testing_registry.py
src/aeat/application/filing/reconciliation/_reconcile.py
src/aeat/application/filing/runtime.py
src/aeat/application/invoices/_linking.py
src/aeat/application/ledger/_id_resolution.py
src/aeat/application/ledger/_models.py
src/aeat/application/live/__init__.py
src/aeat/application/modelo/_history.py
src/aeat/application/operator_surface/_crud_contract.py
src/aeat/application/overview/__init__.py
src/aeat/application/overview/_agenda.py
src/aeat/application/review/_adapters.py
src/aeat/application/review/_edit.py
src/aeat/application/review/_operator.py
src/aeat/application/storage/calc_sheets/_engine.py
```
(43 files total; 30 shown above are the most prominent by count)

## Classification

Many of the 120 sites raise `ValueError` or `TypeError` for programmer-facing
invariant violations (pydantic model validators, internal dispatch fall-throughs,
binding type guards). These are not operator-facing messages and do not require
locale management.

The operator-facing subset is concentrated in:
- `src/aeat/application/filing/` — `ModeloBuilderError`, reconcile errors
- `src/aeat/application/overview/` — `AgendaError`
- `src/aeat/application/review/` — operator-visible review errors
- `src/aeat/application/ledger/` — ledger resolution errors

## Recommendation

Follow-on steps should prioritise the operator-facing subset (filing, overview,
review, ledger) for locale migration. The aggregation, auth, and calculations
`ValueError`/`TypeError` sites are internal invariant guards and can remain as
raw f-strings (they are never rendered to the operator).
