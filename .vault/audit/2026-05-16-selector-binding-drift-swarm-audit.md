---
tags:
  - '#audit'
  - '#selector-binding-drift-swarm'
date: '2026-05-16'
modified: '2026-05-16'
related: []
---

# `selector-binding-drift-swarm` audit: Selector and binding drift

## Scope

Audited the discriminator selector registry (`_BINDING_SELECTOR_REGISTRY`) in
`src/aeat/domain/calculations/registry/_bindings.py` against:

- Every typed `_*Selector` pydantic model defined in the same module
- All TOML binding definitions under `src/aeat/_data/registry/aeat/modelos/`
- Snapshot-build gate wiring in `_snapshot.py` and `_validate.py`
- The `_validate_per_source_binding` validators called from `validate_registry`
- Consumer-side handler code paths that re-validate selectors at call time

The four source kinds intentionally excluded from the discriminator registry
(`ledger`, `rental`, `vat`, `category`) were verified for live TOML usage.

## Inventory

| Source kind | Typed selector class | Live TOML binding count |
|---|---|---|
| `previous_filing` | `_PreviousFilingSelector` | 67 |
| `invoice` | `_InvoiceSelector` | 0 (used via counterpart family) |
| `ledger_transaction` | `_InvoiceSelector` | 0 |
| `purchase_invoice_evidence` | `_InvoiceSelector` | 0 |
| `payable_invoice` | `_InvoiceSelector` | 0 |
| `collectible_invoice` | `_InvoiceSelector` | 17 |
| `ledger_oss_aggregation` | `_OssIossLedgerSelector` | 5 |
| `ledger_iva_aggregation` | `_IvaLedgerSelector` | 22 |
| `ledger_renta_expense_aggregation` | `_RentaLedgerExpenseSelector` | 4 |
| `withholding` | `_WithholdingSelector` | 13 |
| `related_party_operation` | `_RelatedPartySelector` | 6 |
| `foreign_asset` | `_ForeignAssetSelector` | 6 |
| `atribucion_member` | `_AtributionSelector` | 4 |
| `refund_operation` | `_RefundSelector` | 5 |
| `manual_input` | `_ManualInputSelector` | 781 |
| `profile` | `_ProfileSelector` | 36 |
| `ledger` | (free-form, none) | **0** |
| `rental` | (free-form, none) | **0** |
| `vat` | (free-form, none) | **0** |
| `category` | (free-form, none) | **0** |

Note: `invoice`, `ledger_transaction`, `purchase_invoice_evidence`, and
`payable_invoice` show zero live TOML usage. `collectible_invoice` (17
bindings, all in modelo 349) is the only counterpart-family source with live
data in the current registry.

## Findings

### F1 — `validate_binding_selector_shape` and handler selectors are inconsistent for `source`-keyed selectors

`validate_binding_selector_shape` calls `selector_model.model_validate(binding.selector)` on the raw selector
`Mapping`. The individual handler selectors (`_invoice_selector`, `_previous_filing_selector`,
`_ledger_oss_selector`, `_ledger_iva_selector`, `_renta_ledger_expense_selector`, `_manual_input_selector`)
all call `_selector_as_dict(binding)` first, which strips a `source` key from the selector mapping if present.

Consequence: if a selector mapping contains a `source` key (which `extra="forbid"` would reject), the
snapshot-build gate (`_check_binding_selector_shapes`) raises a validation error, but the same binding's
handler succeeds silently because `_selector_as_dict` strips the key before model-validation. The snapshot
gate is therefore _stricter_ than the runtime handler for this class of selectors — the inverse of the
intended relationship. In practice no live TOML binding injects a `source` key, so this is a latent
correctness hazard rather than a current failure, but it will surface as a confusing snapshot-build failure
if any TOML binding or test fixture includes a `source` selector key.

`_withholding_selector`, `_validated_related_party_selector`, `_validated_foreign_asset_selector`,
`_validated_atribucion_selector`, and `_validated_refund_selector` use `binding.selector` directly (no
`_selector_as_dict` call), which is consistent with `validate_binding_selector_shape`. This subset is
internally consistent.

**Fix:** Change `validate_binding_selector_shape` to call `_selector_as_dict(binding)` before passing the
mapping to `selector_model.model_validate`, mirroring the handler-side helpers for the five sources that
already use this path.

---

### F2 — Fact-value invariants for `withholding`, `related_party_operation`, `foreign_asset`, `atribucion_member`, and `refund_operation` are not enforced at snapshot-build time

`_validate_per_source_binding` (called from `RegistryValidator._validate_revision` during `validate_registry`
and `build_snapshot`) enumerates only four semantic validators:
`invoice`, `ledger_oss_aggregation`, `ledger_iva_aggregation`, `ledger_renta_expense_aggregation`.

The remaining nine typed sources have no entry in `source_validators`. In particular:

- `_WithholdingSelector.fact` is declared as `str`, not as `Literal[permitted_values]`. The permitted set is
  `_WITHHOLDING_FACTS = {"row_field", "retencion_sum", "percibido_sum", "perceptor_count"}`. A binding
  with `fact = "arbitrary_string"` passes both `validate_binding_selector_shape` (shape gate accepts any
  non-empty string) and `validate_registry`, but raises `RegistryValidationError` inside
  `_validated_withholding_selector` when the consumer actually calls into the binding at runtime.

- `_RelatedPartySelector`, `_ForeignAssetSelector`, `_AtributionSelector`, and `_RefundSelector` all
  declare `fact: str = Field(min_length=1, max_length=64)`. Their handlers require `fact == "row_field"` but
  no snapshot-build gate enforces this. An invalid fact passes all pre-runtime checks.

**Fix:** Add `validate_withholding_binding_definition`, `validate_related_party_binding_definition`,
`validate_foreign_asset_binding_definition`, `validate_atribucion_binding_definition`, and
`validate_refund_binding_definition` functions (mirroring the existing four) and register them in
`_validate_per_source_binding`. Alternatively, narrow the `fact` field to `Literal[...]` so the shape gate
itself rejects invalid values.

---

### F3 — Counterpart-source semantic invariants (fact/op cross-checks) are not enforced at snapshot-build

The four counterpart sources (`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`,
`collectible_invoice`) share `_InvoiceSelector` for shape validation but have their semantic fact/op
cross-checks in `_validated_counterpart_selector`, which is only called at handler-call time.

`_validate_per_source_binding` does not include any counterpart-source entry. `_check_binding_selector_shapes`
validates the _InvoiceSelector shape but does not enforce:

- `fact == "operator_count"` requires `aggregation.op == "count_distinct"`
- `fact == "rectified_base_delta_sum"` requires `rectification_scope == "only_rectifications"`
- `fact == "row_field"` requires `aggregation.op == "rows"`, a `row_field` key, and a `grouping` key
- `grouping == "operator_clave_period"` requires `rectification_scope == "only_rectifications"`

A counterpart binding that violates these invariants passes `validate_registry` and snapshot-build shape
checks but fails when `_validated_counterpart_selector` is called at handler time. The existing 17 live
`collectible_invoice` bindings are semantically correct (confirmed by code inspection), but the gap means
any future counterpart binding with a malformed fact/op pair would reach production without detection.

**Fix:** Add a `validate_counterpart_binding_definition` validator that delegates to
`_validated_counterpart_selector` and register it for all four counterpart source kinds in
`_validate_per_source_binding`.

---

### F4 — `validate_registry` does not call `_check_binding_selector_shapes`; selector shape errors only surface through `build_snapshot`

`validate_registry` (called from `RegistryValidator.validate_registry`) calls `_validate_modelo` →
`_validate_revision` → `_validate_binding_section` → `_validate_per_source_binding`. None of these paths
call `_check_binding_selector_shapes`, which lives inside `_check_all_id_references`, which is only called
from `_build_validated_snapshot` (triggered by `build_snapshot`).

The consequence: a test or tool that calls `validate_registry` directly (e.g. the registry validator tests)
does not exercise the discriminated-selector shape gate. A malformed selector that is unknown to the four
semantic validators (e.g. a `withholding` binding with an extra key) would pass `validate_registry` but fail
`build_snapshot`. This is an ordering gap rather than a coverage gap — but it means CI tools that validate
the registry without building a snapshot silently skip the shape gate.

`test_referential_integrity.py` does call `_build_validated_snapshot` for snapshot-level checks, so the
shape gate is reachable through that test path. However `validate_registry` as a standalone path does not
reach it.

**Fix:** Call `_check_binding_selector_shapes` from `_validate_revision` (or from `_validate_binding_section`)
so the shape gate fires both during `validate_registry` and during snapshot-build.

---

### F5 — `_is_layout_binding` re-implements layout detection by raw selector key inspection rather than delegating to `_ManualInputSelector`

`_is_layout_binding` in `_validate.py` inspects `binding.selector` directly for the presence of
`{"record", "offset", "length", "data_type"}`. This predicate determines which `source_tier` is required for
a binding's `source_refs`: layout bindings require `"layout_authority"` while semantic bindings require
`"official_source_guidance"`.

Now that `_ManualInputSelector` exists and is registered in the discriminator registry, this predicate should
delegate to the typed model rather than repeat the raw key-membership check. The current implementation would
silently mis-classify a `manual_input` binding if the set of record-shape keys in `_ManualInputSelector` ever
changed, because `_is_layout_binding` is not coupled to the model's source of truth.

Concretely: if `_ManualInputSelector._validate_manual_input_shape` were updated to rename `offset` or add a
new required record-shape key, `_is_layout_binding` would not see the change and would either over-include or
under-include bindings in the layout tier.

**Fix:** Parse the binding's selector through `_ManualInputSelector` (or a lightweight variant) and use the
resulting `record is not None` flag from the typed model to determine whether the binding is a layout binding,
removing the raw set-intersection logic from `_is_layout_binding`.

---

### F6 — `test_free_form_source_returns_no_diagnostics` has a stale docstring naming `manual_input` and `profile` as untyped

The test at `test_selector_shape.py:189-201` is titled `test_free_form_source_returns_no_diagnostics` and its
docstring states:

> Sources like `manual_input` and `profile` are not yet typed in the discriminator registry; the gate must
> return an empty failure list for them so existing registry data keeps loading.

Both `manual_input` and `profile` are now fully typed and registered in `_BINDING_SELECTOR_REGISTRY`. The
test itself uses `source="ledger"` (which is correctly unregistered) so the assertion still passes, but the
docstring misleads readers into believing the typed-selector project is incomplete for these two sources
when it is not. Similarly, the module docstring at line 12 states "ten typed sources" but the registry
currently has 16.

**Fix:** Update the test docstring to name `ledger`, `rental`, `vat`, and `category` as the intentionally
free-form sources. Update the module docstring to reflect the current count (16 typed sources).

---

### F7 — `party_legal_name` as `row_field` under `operator_clave` grouping is accepted at snapshot-build but fails at runtime when observations have no legal name

`_InvoiceRowField` includes `"party_legal_name"`. The consumer (`_build_operator_clave_rows`) only inserts
`party_legal_name` into the row dict when `observation.party_legal_name is not None`. If the key is absent and
a binding declares `row_field = "party_legal_name"`, the consumer raises `RegistryValidationError`:

```
f"binding {binding.id!r} row_field {selector.row_field!r} not produced for grouping {grouping!r}"
```

`_validate_invoice_fact_and_aggregation` (called by `_validate_per_source_binding` for the `invoice` source)
does not check whether `party_legal_name` is safe to use with `grouping == "operator_clave"`. The same gap
applies to `operator_clave_period` rows. No static invariant prevents a registry author from writing a binding
that is syntactically valid but fails deterministically at runtime whenever an observation has no legal name.

There are currently zero live TOML bindings using `row_field = "party_legal_name"` (confirmed by grep across
the full TOML corpus), so this is a latent hazard. The selector permits a shape the runtime cannot always
fulfill.

**Fix:** Either document `party_legal_name` as an optional row field (and update the consumer to return a
sentinel value or empty string) or add a validation invariant in `_validate_invoice_fact_and_aggregation`
that rejects `row_field = "party_legal_name"` unless the registry binding explicitly opts into optional-field
handling.

## Recommendations

- **P1 (low risk, high clarity):** Fix F1 by routing `validate_binding_selector_shape` through `_selector_as_dict`
  for the five sources that already strip the `source` key in their handlers. This removes the latent
  snapshot-fail / handler-pass asymmetry.

- **P2 (medium risk, closes semantic gap):** Fix F2 by narrowing the `fact` field from `str` to
  `Literal[permitted_values]` in `_WithholdingSelector`, `_RelatedPartySelector`, `_ForeignAssetSelector`,
  `_AtributionSelector`, and `_RefundSelector`. This promotes handler-side fact invariants into the shape gate
  at zero runtime cost.

- **P3 (medium risk, closes counterpart gap):** Fix F3 by adding a counterpart-specific validator to
  `_validate_per_source_binding` so that the fact/op invariants from `_validated_counterpart_selector` are
  enforced at snapshot-build rather than only at call time.

- **P4 (low risk, closes ordering gap):** Fix F4 by moving `_check_binding_selector_shapes` into
  `_validate_revision` (or calling it from `_validate_binding_section`) so it fires for every path that
  calls `validate_registry`, not only for `build_snapshot`.

- **P5 (low risk, removes drift vector):** Fix F5 by replacing the raw key-intersection in `_is_layout_binding`
  with a delegation to `_ManualInputSelector`'s typed model, so layout detection remains in sync with the
  selector schema without manual upkeep.

- **P6 (no risk, documentation):** Fix F6 by updating the stale test docstring and module-level count
  in `test_selector_shape.py` to reflect the current registry (16 typed sources, free-form remainder is
  `ledger`/`rental`/`vat`/`category`).

- **P7 (requires design decision):** Fix F7 by deciding whether `party_legal_name` is a required or optional
  row field and encoding that decision either in the `_InvoiceRowField` Literal (remove it if always optional
  and handled by callers) or in a new cross-field invariant in `_validate_invoice_fact_and_aggregation`.
