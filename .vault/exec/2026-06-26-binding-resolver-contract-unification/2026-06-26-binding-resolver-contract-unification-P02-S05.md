---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S05'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---




# Promote the profile mesh resolver result onto CalculationSourceResolution and drop the ProfileSourcedBindingResult wrap, keeping the date-binding and provenance channels intact

## Scope

- `src/aeat/application/modelo/_profile_binding.py`

## Description

- Change `resolve_profile_sourced_bindings` to return the canonical `CalculationSourceResolution` directly, building one `CalculationSourceProvenance` row per profile-sourced binding inline (source_kind `profile`, source_ref `profile:{bucket}:binding:{id}`, profile-record fingerprint).
- Delete the `ProfileSourcedBindingResult` wrap class and drop it from the module and package `__all__`.
- Keep the date-binding channel and the per-binding provenance trace intact; the three empty-return paths now yield an empty profile resolution carrying the `profile` owned source.
- Simplify `ProfileSourceResolver.resolve` to delegate straight to `resolve_profile_sourced_bindings` (no re-wrap).
- Re-point `_binding_readiness` to compute the sourced-binding set from the resolution's three channel key-unions instead of the retired `bindings_sourced_from_profile` field.

Modified files: `src/aeat/application/modelo/_profile_binding.py`, `src/aeat/application/aggregation/_source_profile.py`, `src/aeat/application/modelo/_binding_readiness.py`, `src/aeat/application/modelo/__init__.py`.

## Outcome

Landed in the atomic S05+S06+S08 commit `0d825d774`. Profile facts now flow on the single `CalculationSourceResolution` envelope with no intermediate wrap, preserving the Decimal / enum / date channels and the provenance trace. The `test_profile_binding` suite migrated to read the resolution's channel union; the two obsolete wrap-validator tests were deleted per no-legacy. Full-calc E2E (M130->M100, M303->M390, recargo, pull-vs-calculate parity) and the binding suite stayed green with no casilla value shift.

## Notes

The profile precedence stays lowest in the ladder, preserved byte-identically by the dict-merge in `_binding_resolution`. The provenance source_kind / source_ref / fingerprint strings are unchanged from the prior `ProfileSourceResolver` output, so no provenance regression.
