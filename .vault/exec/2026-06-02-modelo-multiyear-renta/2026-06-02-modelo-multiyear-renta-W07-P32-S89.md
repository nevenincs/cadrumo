---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S89'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# investigate and implement or explicitly supersede the Modelo 721 per-custodian prior-year baseline binding promised by the accepted ADR

## Scope

- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py` (investigation)
- `src/aeat/domain/calculations/registry/tests/test_modelo_721_registry.py`
- `src/aeat/application/calculations/tests/test_modelo_721_cripto_extranjero_fidelity.py`
- `.vault/adr/2026-06-02-modelo-721-cripto-data-fidelity-adr.md`

## Description

- Ground the open S89 question with vault RAG over the accepted Modelo 721 ADR and
  code RAG over `previous_filing` selector resolution and the foreign-asset
  re-declaration helper.
- Verify the live `previous_filing` resolver rejects `source_output`, consumes
  `source_casilla_id` / `source_casilla_ids`, and returns scalar `BindingId ->
  Decimal` values from the `casilla_values` view.
- Verify Modelo 721 row identity is carried by ordered
  `RegistryModeloObservation.observations`, while repeated row casillas collapse in
  the scalar `casilla_values` mapping.
- Supersede the accepted ADR's obsolete Modelo 721 `source_output` binding clause in
  favor of the landed row-observation advisory mechanism.
- Add M721-specific regression coverage so the registry cannot grow a fake scalar
  `previous_filing` binding for token continuity and the fidelity test pins the
  ordered-row boundary.

## Outcome

- The promised Modelo 721 per-custodian `previous_filing` binding is explicitly
  superseded, not implemented.
- The live continuity path remains the row-observation advisory helper tested across
  two annual cycles.
- A future registry-native row-set baseline is left as a new ADR/schema-resolver
  problem rather than hidden inside the scalar previous-filing contract.

## Notes

- No legal ambiguity was reopened in this step; the change concerns the implementation
  channel for the already accepted Modelo 721 threshold-continuity decision.
- No fallback binding was authored.
