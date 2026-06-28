---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S11'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# run every family validator from the single dispatch table inside the registry-build section validator so all families are checked at snapshot build

## Scope

- `src/aeat/domain/calculations/registry/_bindings.py`

## Description

- Confirm the registry-build section validator (`validate_binding_section` in `_validate_record_sections.py`) runs `validate_binding_selector_shape` for every binding, which now routes through the single `_BINDING_VALIDATOR_REGISTRY` table so every family validator runs in one accumulating pass at snapshot build.
- Remove the redundant `_validate_per_source_binding` helper and its per-binding call: the separate try/except calls to the raising `validate_invoice_binding_definition` and the four `validate_ledger_*_binding_definition` functions are now subsumed by the single dispatch loop (the invoice strict validator and the four ledger validators are in the table).
- Drop the now-unused imports (`RegistryValidationError`, `INVOICE_BINDING_SOURCE_KINDS`, the five raising validators) from `_validate_record_sections.py`.

## Outcome

There is now one binding-validation path at registry build: the section validator's single `validate_binding_selector_shape` loop, accumulating every family's failures in one pass. The dual path (list-returning selector gate plus separate raising per-source calls) is gone. The resolve-time raising validators remain in `_invoice_bindings.py` / `_ledger_bindings.py` as defence-in-depth re-checks.

## Notes

The three invoice-shaped sources are routed to the stricter `validate_invoice_binding` (the union of the prior dual path); `ledger_transaction`, a counterpart-only source, keeps `validate_counterpart_binding`. Committed in `refactor(registry): one binding validator contract (W02.P03)` alongside the dispatch table it depends on.
