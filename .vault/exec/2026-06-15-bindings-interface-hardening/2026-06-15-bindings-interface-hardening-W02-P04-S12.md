---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S12'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# add build-time rejection tests per family plus an anti-tautology proof asserting a malformed binding fails at build for each family, not only at resolve

## Scope

- `src/aeat/domain/calculations/registry/tests/test_binding_build_validation.py`

## Description

- Add `test_binding_build_validation.py` with a parameterised per-family case table covering all ten validated families (invoice, counterpart, the four ledger families, the four detail-record families, withholding, previous_filing), each carrying a well-formed and a malformed selector plus a stable diagnostic fragment.
- For each family, assert the malformed binding is REJECTED at registry-build by injecting it into the committed Modelo 130 modelo and running `RegistryValidator.validate_modelo`, asserting the lifted-invariant fragment and the binding id appear in the raised `RegistryValidationError`.
- Add the anti-tautology pair: assert a well-formed binding of each family passes the dispatch gate (`validate_binding_selector_shape` returns empty), and assert the malformed binding is a constructible `DataBindingDefinition` (so the rejection is the build gate's lifted invariant, not a pydantic schema refusal).
- Add a dispatch-coverage test and an isolated revision-level gate test exercising the single `validate_binding_selector_shape` path per family.

## Outcome

Thirty-two tests pass. Each family's malformed binding fails at registry-build (snapshot-construction validation), not only at resolve, and each family's well-formed binding passes — proving the gate is live and not trivially rejecting everything.

## Notes

The two ledger families need fully-formed substrate selectors; the well-formed cases reuse the real committed M349 OSS selector and M130 renta-income selector shapes. The ledger-renta-income malformed case trips the typed selector Literal (a `selector violates` build-time rejection); the OSS malformed case carries a complete selector with the wrong op so it trips the lifted aggregation-op invariant. Committed in `feat(registry): enforce binding validation at build for all families (W02.P04)`.
