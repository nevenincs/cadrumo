---
step_id: S218
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-P17-S67]]"
---

# cross-domain-continuity P14.S218 — Fix M200 verify ModeloBuilderError for legal_entity_form enum binding

## Root cause

`build_filing_draft` in `src/aeat/application/filing/__init__.py` routed all
formula binding IDs through `_decimal_inputs_for_ids`, which calls
`Decimal(value)` on each input. The M200 binding
`modelo-200-2024-profile-legal-entity-form` is consumed as a string enum
(`"sl"` / `"sa"`) by the `lookup_parameter_by_entity_type` dispatch op.
`Decimal("sl")` raises `InvalidOperation`, which was re-raised as
`ModeloBuilderError: input 'modelo-200-2024-profile-legal-entity-form' must
be a Decimal value`.

A secondary crash site existed in `_filing_binding_values`, which also
called `_binding_input` on the enum binding and defaulted to the Decimal
coercion path because the binding selector has no `data_type` field.

## Fix

Two-site patch in `src/aeat/application/filing/__init__.py`:

1. Import `enum_consumed_binding_ids` from the registry module.
2. In `build_draft` (formerly `build_filing_draft`): split
   `calculation_binding_ids` into `decimal_binding_ids` (subtracting
   `enum_binding_ids`) and collect string values for enum bindings via the
   new `_string_inputs_for_ids` helper. Pass these to
   `calculate_registry_snapshot` via `enum_binding_values`.
3. In `_filing_binding_values`: skip any `binding_id` that is in
   `enum_binding_ids`; these bindings carry no fichero-BOE addressing and
   must not be Decimal-coerced.
4. Added `_string_inputs_for_ids(inputs, input_ids)` helper that extracts
   only `str`-valued entries for a given ID set.

## Test coverage

`src/aeat/application/filing/test_decimal_inputs_routing.py` (new, 4 tests):

- `test_enum_consumed_binding_ids_identifies_legal_entity_form` — pins that
  the registry discriminator classifies this binding as enum-routed.
- `test_string_inputs_for_ids_extracts_enum_binding` — unit test for the
  new helper.
- `test_filing_binding_values_skips_enum_bindings` — pins that the
  `_filing_binding_values` path does not attempt Decimal coercion.
- `test_calculate_registry_snapshot_accepts_enum_binding_via_enum_channel` —
  full calculation path with `enum_binding_values` supplied; asserts
  `DP200014:00562 == 23000.00` (AEAT M200 manual 2024, Art. 29 LIS).

All 4 tests pass. Ruff clean.

## Files changed

- `src/aeat/application/filing/__init__.py` — enum routing fix (two sites)
- `src/aeat/application/filing/test_decimal_inputs_routing.py` — new regression test file
