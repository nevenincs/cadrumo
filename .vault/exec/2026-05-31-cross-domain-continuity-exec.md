---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'HANDOFF-AUDIT-F1-F5'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-16-cross-domain-handoffs-swarm-audit]]"
  - "[[2026-05-21-cross-domain-handoffs-swarm-audit]]"
---


# `cross-domain-continuity` — cross-domain handoff provenance audit closures (F1-F5)

Repair and test closure for the 5 provenance-loss findings from the 2026-05-16
cross-domain handoffs swarm audit across ledger-to-renta and modelo-to-filing
handoff surfaces.

## Finding F1 — build_draft identity test fixture repair

**Source audit:** `2026-05-16-cross-domain-handoffs-swarm-audit.md` F1.
**Surface:** `src/aeat/application/filing/test_build_draft_identity.py`
**Commit:** `621f1006f`

The P07.S36 previous-filing-bound casilla smuggling guard (added to
`_formula_runtime.py`) broke the existing `build_draft` identity contract
test. Casilla `"15"` in M130 is bound via `previous_filing` source
(`modelo-130-resultados-negativos-anteriores`). Supplying it directly in
the flat `inputs` dict without a matching `binding_values` entry now raises
`RegistryValidationError`. For Q1 the binding is absent-by-design (no prior
trimestre in the same ejercicio); the formula engine materialises it as
`Decimal("0")` automatically via the absent-by-design path.

Removed `"15": Decimal("0")` from the test's input dict and added an
explanatory comment.

**Test pass result:** 1 passed in 45s.

## Finding F2 — relation-prefill provenance contract tests

**Source audit:** `2026-05-16-cross-domain-handoffs-swarm-audit.md` F2.
**Surface:** `src/aeat/application/calculations/test_relation_prefill_source_mesh.py`
**Commit:** `557b30fcd`

The bare `except Exception` in `resolve_relations_from_local_store` was already
narrowed to `except RegistryValidationError` with a structured warning log
(commit `720e91dc5`). Two new behavioral tests pin the contract:

- `test_resolve_relations_returns_operator_manual_blanks_when_local_store_is_empty`:
  asserts empty local store returns all-None relation values without raising.
- `test_resolve_relations_produced_values_carry_provenance_string_when_resolved`:
  asserts resolved relation values carry `provenance='local_filing'` string.

These prove the modelo-to-filing handoff preserves relation provenance.

**Test pass result:** 3 passed in 21s (including existing test).

## Finding F3 — typed SpendingCategory survives ledger-to-renta handoff

**Source audit:** `2026-05-16-cross-domain-handoffs-swarm-audit.md` F3.
**Surface:** `src/aeat/application/aggregation/test_renta_ledger_aggregation.py`
**Commit:** `ace73d7ea`

The code fix (`category_id: _SpendingCategoryField | None` via `BeforeValidator`)
was already in `_models.py` (commit `73c017737`). Added a dedicated test:

- `test_casilla_aggregation_category_id_is_typed_spending_category_instance`:
  asserts `isinstance(row.category_id, SpendingCategory)` and `is
  SpendingCategory.CUOTAS_AUTONOMOS_SS`. If `category_id` reverts to bare
  string, the `isinstance` assertion fails, surfacing the regression.

**Test pass result:** 11 passed in 1.85s.

## Finding F4 — FilingRecordCatalogue direct-equality comparison

**Source audit:** `2026-05-16-cross-domain-handoffs-swarm-audit.md` F4.
**Surface:** `src/aeat/domain/modelos/_filing_record.py`
**Commit:** `720e91dc5` (code fix already landed)

The `str(record.modelo) == modelo` comparisons in `current_for` and
`history_for` were replaced with direct `record.modelo == modelo` equality
(removing `str()` coercion) in commit `720e91dc5`. The existing roundtrip
test at `src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py`
exercises both `current_for` and the supersession chain, covering this surface.

**Test pass result:** 2 passed (roundtrip suite).

## Finding F5 — row-set assembly non-fabrication contract

**Source audit:** `2026-05-16-cross-domain-handoffs-swarm-audit.md` F5.
**Surface:** `src/aeat/application/calculations/test_row_set_assembly.py`
**Commit:** `c44434b55`

The fabricated-default strings (`"ES"`, `"A"`, `"01"`, `"UNKNOWN"`) were
replaced by `_optional_text_kwarg` which omits the kwarg entirely when the
row does not supply it (commit `720e91dc5`). Added a dedicated test:

- `test_assemble_withholding_missing_nif_raises_not_fabricates`: supplies a
  row missing `perceptor_tax_id` and asserts `RegistryValidationError` is
  raised with a message containing `perceptor_tax_id`. If the assembler
  silently defaults to an empty or fabricated NIF, the error would not be
  raised and the test would fail.

**Test pass result:** 13 passed in 20.5s (including 12 existing tests).

## Overall gate run

All 5 finding surfaces pass:
- `src/aeat/application/filing/test_build_draft_identity.py` — 1 passed
- `src/aeat/application/aggregation/test_renta_ledger_aggregation.py` — 11 passed
- `src/aeat/application/calculations/test_relation_prefill_source_mesh.py` — 3 passed
- `src/aeat/application/calculations/test_row_set_assembly.py` — 13 passed
- `src/aeat/domain/modelos/test_calculation_repository_roundtrip.py` — 2 passed
- `src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py` — 2 passed

32 total, 0 failures.
