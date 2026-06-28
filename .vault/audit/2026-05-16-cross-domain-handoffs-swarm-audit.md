---
tags:
  - '#audit'
  - '#cross-domain-handoffs-swarm'
date: '2026-05-16'
modified: '2026-05-16'
related: []
---

# `cross-domain-handoffs-swarm` audit: `Cross-domain handoffs`

## Scope

Audited cross-domain data handoffs across the following domain modules and
application-layer adapters in `src/aeat/`:

- `domain/calculations/registry/` — registry snapshot, bindings, relations
- `domain/filing/` — FilingDraft, FilingValue, FilingBindingValue
- `domain/modelos/` — WorkUnit, CalculationRevision, FilingRecord, FilingRecordCatalogue
- `domain/renta/` — RentaDeductibleExpenseObservation
- `domain/transactions/` — Transaction, TransactionCatalogue
- `domain/invoices/` — InvoiceCatalogue
- `domain/vat/` — IvaLedgerObservation
- `application/aggregation/_renta_ledger.py`
- `application/aggregation/_iva_ledger.py`
- `application/aggregation/_models.py`
- `application/calculations/_row_set_assembly.py`
- `application/calculations/_relation_prefill.py`
- `application/filing/__init__.py` (build_draft)
- `application/filing/runtime.py`
- `application/modelo/_actions.py`
- `application/storage/calc_sheets/_engine.py`

The audit looked specifically for: lossy projections via `model_dump(mode="json")`,
string coercion of typed IDs, dict-flattening of typed observations, magic-key
dict access where typed attributes should be used, and disjoint identity propagation
across domain seams.

---

## Findings

### F1 — `build_draft` drops `subject_tax_id` and `snapshot_ref` at construction

**File:** `src/aeat/application/filing/__init__.py` lines 182–200

**Data lost:** The `FilingDraft` model declares two typed fields — `subject_tax_id:
SubjectTaxId | None` and `snapshot_ref: RegistrySnapshotRef | None` — that carry
identity-validated tax identity and the four-axis registry coordinate. The `build_draft`
function constructs `FilingDraft` without supplying either field. Both default to
`None`. Consequently every draft produced by `build_draft` has:

- `subject_tax_id = None` — the AEAT-checksum-validated identity of the filing subject
  is absent. Any downstream consumer that attempts to re-validate the draft's identity
  or re-derive the `draft_id` cannot do so without re-loading the profile.
- `snapshot_ref = None` — the snapshot's typed four-axis registry coordinate
  (`modelo`, `revision_id`, `filing_year`, `period`) is absent. This makes
  the draft impossible to re-resolve against the live registry without the opaque
  `schema_version` string, defeating the purpose of `RegistrySnapshotRef`.

The existing `test_cross_boundary_roundtrip.py` tests assert that both fields
*exist* on the model but do not verify that `build_draft` actually populates them.

**Remediation:** Pass `subject_tax_id=profile.tax_id` (validated via `SubjectTaxId`)
and `snapshot_ref=RegistrySnapshotRef(modelo=snapshot.modelo.id, revision_id=snapshot.revision.id, filing_year=snapshot.filing_year, period=snapshot.period)` at the `FilingDraft(...)` construction site.

---

### F2 — `_relation_prefill.py` silently swallows all resolver exceptions

**File:** `src/aeat/application/calculations/_relation_prefill.py` lines 112–127

**Data lost:** `resolve_relation_values_from_observations` can raise for legitimate
structural reasons (unknown source model, type mismatches, missing casilla outputs).
The bare `except Exception: resolved_map = {}` catches all of these, downgrades them
silently to empty, and sets every relation's `provenance` to `"operator_manual"`.
The downstream engine emits blank cells the operator must fill by hand — with no
audit trail, no warning logged, and no structured error surface for the caller. The
provenance annotation `"operator_manual"` is indistinguishable from the case where
the operator genuinely has no prior filings, so the loss is invisible.

Additionally, `str(relation.source_modelo)` at line 66 and 150 strips typing from
`ModeloId` before passing to the repository. `ModeloId` is a `NewType` or `Annotated`
alias; coercing to `str` bypasses any future type-level guards.

**Remediation:** Narrow the `except` clause to the specific exceptions
`resolve_relation_values_from_observations` is documented to raise (e.g.,
`RegistryValidationError`). Log or surface the failure reason as structured
provenance on the `RelationValue` so callers can distinguish "never filed"
from "resolution failed". Replace `str(relation.source_modelo)` with direct
attribute access once `ModeloId` is a proper typed wrapper.

---

### F3 — `_casilla_aggregation` flattens typed `RentaDeductibleExpenseObservation` tuples to `dict[str, Decimal]`

**File:** `src/aeat/application/aggregation/_renta_ledger.py` lines 508–536

**Data lost:** The aggregation loop (`_casilla_aggregation`) receives a
`Sequence[RentaDeductibleExpenseObservation]` and reduces it to
`casilla_values: dict[str, Decimal]`. Each `RentaDeductibleExpenseObservation`
carries:

- `transaction_id` — the originating ledger transaction
- `category` — the `SpendingCategory` enum member
- `deductible_amount` — the post-profile-adjusted amount
- `target_casilla` — the casilla code

The `CasillaAggregation` model carries a `provenance` tuple of `CasillaProvenance`
rows, each of which records `transaction_ids` and `subtotal` but drops `category`
at the grouped level — the category is stored only as a plain `str` via
`observation.category.value`. The typed `SpendingCategory` enum member is not
preserved in `CasillaProvenance`. Any downstream consumer that needs to filter
provenance by category must re-parse the string through `normalize_spending_category`
rather than compare against the typed enum directly.

**Remediation:** Add a `category: SpendingCategory` field to `CasillaProvenance`
alongside the existing `category_id: str | None`. Populate it during
`_casilla_aggregation` from `observation.category` (not `.value`). This makes
the provenance trace strongly typed end-to-end without changing the serialised
output (the `category_id` string stays for backward compatibility).

---

### F4 — `FilingRecordCatalogue` and `WorkUnitCatalogue` compare `record.modelo` with `str(record.modelo)` instead of typed equality

**Files:**
- `src/aeat/domain/modelos/_filing_record.py` lines 219, 252, 273
- `src/aeat/domain/modelos/_work_unit.py` line 213

**Data lost:** Both `FilingRecordCatalogue.current_for` and
`FilingRecordCatalogue.history_for` use `str(record.modelo) == modelo` where
`modelo` is a plain `str` parameter. If `record.modelo` is a `ModeloCode` enum
member (which it is — the field is typed `ModeloCode`), the comparison works but
only because `ModeloCode` is a `StrEnum`. Any refactor that makes `ModeloCode`
a non-string typed ID (e.g., a `NewType[str]` with validation) would break these
comparisons silently. The same pattern appears in `_enforce_keys_match` and
`_enforce_derived_id` on `WorkUnit`. The `_actions.py` sort key at line 1779
and `_export.py` lines 218/227/270/309 repeat the pattern.

**Remediation:** Accept `ModeloCode` (or a union `ModeloCode | str`) at the
method signatures. Compare `record.modelo` directly against a `ModeloCode` value
rather than coercing via `str()`. Where callers pass bare strings, add a
`ModeloCode(modelo)` coercion at the boundary rather than at each comparison site.

---

### F5 — `_row_field_lookup` and `_cells_by_row` use dict-style `.get` access on typed `Mapping` selectors; unknown keys silently yield `None`

**File:** `src/aeat/application/calculations/_row_set_assembly.py` lines 159–169

**Data lost:** `_row_field_lookup` calls `binding.selector.get("row_field")` on
each binding. The `binding.selector` is typed `Mapping[str, Any]` on
`DataBindingDefinition`. If a registry author omits `"row_field"` from a
`rows`-aggregation binding selector, `get` returns `None` and the binding is
silently skipped — the column is not assembled, and no warning is surfaced to
the caller. The assembler functions (`assemble_withholding_observations`, etc.)
also use `fields.get(...)` with positional defaults that substitute `"ES"`,
`"A"`, `"01"`, `"UNKNOWN"` — fabricated legal values — when fields are missing,
rather than rejecting the row.

Similarly, `binding.aggregation.get("op")` at line 164 (and `_engine.py` lines
787–793) uses `(binding.aggregation or {}).get("op")` — a bare dict access on
an untyped `Mapping`. If the TOML selector introduces a spelling variant (e.g.,
`"operation"` instead of `"op"`), the binding is silently excluded from all row
assembly without any structural validation.

**Remediation:** Introduce typed `RowProducerSelector` and `RowAggregation`
pydantic models with required `row_field`, `grouping`, and `op` fields. Validate
these at registry load time in `_validate.py` so a missing `row_field` is caught
before it reaches the assembler. In the assemblers, reject (rather than silently
default) rows whose mandatory fields (`perceptor_tax_id`, `member_tax_id`,
`counterparty_tax_id`) are empty strings, since these are AEAT-required fields.

---

### F6 — `IvaLedgerAggregation` drops `prorrata_reference` linkage from `IvaLedgerObservation`; cross-domain traceability gap

**File:** `src/aeat/application/aggregation/_iva_ledger.py` lines 263–273

**Data lost:** The `aggregate_iva_ledger_observations` function produces two
parallel output sequences: `observations` (`IvaLedgerObservation`) and
`prorrata_references` (`ProrrataLedgerReference`). The `IvaLedgerObservation`
model has no back-reference to its associated `ProrrataLedgerReference`. When
the prorrata path fires (`flow_direction is SOPORTADO` and a `prorrata_reference`
is set), the function appends to *both* lists, but the linkage between the
observation and the prorrata reference is implied only by matching
`transaction_id` — which requires callers to join the two sequences manually
by identity key.

Downstream Modelo 303 / 390 binding consumers (`_bindings.py` `_IvaLedgerSelector`)
only receive the `IvaLedgerObservation` tuple. They have no access to the prorrata
reference, so the prorrata deduction factor is not applied at the observation level.
The prorrata calculation is handled separately (in `_prorrata.py`) but the connection
between a specific observation and its prorrata reference is not enforced by type.

**Remediation:** Add an optional `prorrata_reference_id: str | None` field to
`IvaLedgerObservation`, populated from `transaction.transaction_id` when a
validated `ProrrataLedgerReference` is produced for the same transaction. This
makes the linkage explicit and type-checked, allowing binding selectors to filter
or annotate prorrata-linked observations without a manual join.

---

### F7 — `_relation_prefill.py` uses `str(relation.source_modelo)` at the repository boundary, stripping `ModeloId` typing

**File:** `src/aeat/application/calculations/_relation_prefill.py` lines 66, 150

**Data lost:** `RelationDefinition.source_modelo` is typed `ModeloId` (an alias
for `str` with registry validation in the schema). At line 66,
`repository.iter_modelo(str(relation.source_modelo))` coerces it to a plain
`str`. The same occurs at line 150 inside `_provenance_note`. `ModeloId` carries
the constraint that the value is a known, validated modelo identifier. Stripping
it to bare `str` means the repository call is not type-checked against the
`ModeloId` constraint. The same pattern appears in `_relations.py` line 68 and
`_engine.py` line 787–793.

This mirrors the already-identified and partially remediated `str(work_unit.modelo)`
pattern referenced in the audit brief. The `_relation_prefill` path was not
included in that remediation pass.

**Remediation:** Change `iter_modelo` (and similar repository methods) to accept
`ModeloId` directly. Remove all `str(relation.source_modelo)` coercions in
`_relation_prefill.py`, `_relations.py`, and `_engine.py`. This is a low-effort
mechanical change that restores type-level identity propagation across the
prefill → registry → repository seam.

---

## Recommendations

1. **Prioritise F1 (`build_draft` dropping `subject_tax_id` and `snapshot_ref`).**
   This is a silent identity loss at the most visible seam in the codebase. Every
   draft produced today is missing validated tax identity and the typed registry
   coordinate. The fix is two extra constructor arguments; the test surface in
   `test_cross_boundary_roundtrip.py` already has the gate shape, it just needs
   to assert non-None values from `build_draft`.

2. **F2 (bare `except Exception` in `_relation_prefill.py`) is a correctness risk.**
   A mis-typed TOML relation that causes `resolve_relation_values_from_observations`
   to raise will silently produce operator-manual blanks in the calc sheet, and the
   operator has no feedback. Narrow the catch and add structured logging.

3. **F4 (`str(record.modelo)` comparisons) and F7 (`str(relation.source_modelo)`)
   are mechanical regressions of the recently cleaned `str(work_unit.modelo)` pattern.**
   They should be bundled into the same elimination pass.

4. **F3 (typed `SpendingCategory` dropped to string in `CasillaProvenance`) and
   F5 (untyped `Mapping` access in row-set assembly) are lower priority** but
   represent structural drift: the codebase has established patterns for typed
   observation records and validated selectors; these seams are not yet using them.

5. **F6 (prorrata reference not linked to observation)** is a domain-model gap.
   The fix requires a minor schema addition to `IvaLedgerObservation`. Until then,
   any consumer that needs to apply the prorrata deduction per-observation must
   perform an unsafe join.
