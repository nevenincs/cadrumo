---
step_id: S29
tags:
  - '#exec'
  - '#calculation-engine-foundations'
date: '2026-06-10'
related:
  - '[[2026-06-10-calculation-engine-foundations-plan]]'
  - '[[2026-06-10-calculation-engine-foundations-audit]]'
---

# `calculation-engine-foundations` `W04.P12.S29` exec

## Step

`W04.P12.S29` — Lock pull-path == calculate-path casilla parity for a shared revision.

Scope: `application/calculations/tests`.

## Outcome: B — Structurally Unified / Divergence Prevented

After W03, both the live bucket-aggregation calculate path and the standalone relay path
share one implementation — `resolve_relations_from_local_store` — so divergence at the
relation-resolution boundary is structurally impossible. The test documents and locks
that structural guarantee.

## Structural Analysis

**Two paths compared for F5:**

1. **Live calculate path** (`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`):
   enrolls `RelationPrefillSourceResolver` in its `merge_source_resolutions` mesh, which
   delegates to `resolve_relations_from_local_store`. The materialised binding values ride
   through `source_resolution.binding_values` → `backend_binding_values`, and the resolved
   relation values go through `source_resolution.relation_values` → `merged_relation_values`
   into `calculate_registry_snapshot`.

2. **Standalone relay path** (`RelationPrefillSourceResolver.resolve()` +
   `calculate_registry_snapshot` directly): calls `resolve_relations_from_local_store`
   via the same `RelationPrefillSourceResolver`, then feeds `binding_values` and
   `relation_values` directly into `calculate_registry_snapshot`.

Both paths converge on the same function (`resolve_relations_from_local_store`) for
relation resolution and the same formula engine (`calculate_registry_snapshot`) for
computation. The existing `test_relation_prefill_source_mesh.py` already proved that
`RelationPrefillSourceResolver.resolve()` returns the same `relation_values` as
`resolve_relations_from_local_store()`. This step adds the end-to-end parity proof at
the casilla_values level.

**Why no divergence is possible**: The `_formula_initial_values._binding_is_absent_by_design`
function treats unresolved `relation_prefill` bindings as absent-by-design (returns zero),
so a `relation_prefill` BOUND casilla whose value is omitted from `binding_values` does
NOT raise. Since both paths always provide the materialised binding values (the live path
via the mesh; the relay path via `relay_resolution.binding_values`), both paths fill the
BOUND casillas from the same source values.

## What was done

Added `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`
with one test:

**`test_pull_path_and_calculate_path_share_resolver_and_produce_equal_casilla_values`**

Seeds four distinct M115 quarterly filed observations (1T: 2 perceptores / 1200 EUR base,
2T: 3 / 1350, 3T: 2 / 900, 4T: 2 / 1100 — summing to 9 perceptores and 4550 EUR total
base) into a real encrypted-SQLite `CalculationObservationRepository`. Then:

- **Path A (live)**: creates a M180 work unit + calls
  `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` (full mesh, real
  `WorkUnitCatalogueRepository`, `CalculationRevisionCatalogueRepository`,
  `TransactionCatalogueRepository`, `InvoiceCatalogueRepository`).

- **Path B (relay)**: calls `RelationPrefillSourceResolver.resolve()` against the same
  observation store, then calls `calculate_registry_snapshot` with the resolved
  `binding_values` and `relation_values`.

Asserts:
- All shared casillas between the two paths are equal (divergence dict is empty).
- The M180 summary casillas (`decl.total-perceptores`, `decl.base-total`,
  `decl.retenciones-total`) equal the expected totals derived from the registry engine
  applied to the four seeded quarters — a non-tautological oracle (AEAT 180/115
  reconciliation: total annual = sum of four quarters).
- The relay path's `relation_values` equal `resolve_relations_from_local_store()`
  independently — confirming both paths share one resolver.

**Real adapters**: real encrypted SQLite, real `isolated_runtime_profile`, real registry
authority, real formula engine. No mocks, no skips, no xfail.

**Non-tautological**: expected values derived from the registry engine applied to seeded
per-quarter inputs, not hand-computed from the same formula under test.

## Verification

```
uv run --no-sync pytest src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py -v
# → 1 passed in 2.68s

uv run --no-sync pytest src/aeat/application/storage/calc_sheets/tests/ \
  src/aeat/application/modelo/tests/ \
  src/aeat/application/calculations/tests/ \
  -q --no-header -p no:cacheprovider
# → 787 passed; 12 failed (all pre-existing peer failures:
#   - test_bucket_aggregation_flow.py (3) — negative RawTransaction.amount validation
#   - test_modelo_filing_snapshot_coverage.py (5) — same
#   - test_simplificado_ledger_bypass.py (2) — same
#   - test_cross_period_clean_state.py (1) — justificante-classification
#   - test_modelo_303_special_case_casilla_routing.py (1) — negative RawTransaction.amount)

uv run --no-sync pytest ... --collect-only -q
# → 799 tests collected (798 baseline + 1 new)

ruff check src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py
# → All checks passed!

ty check src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py
# → All checks passed!
```

## Commit

`cb300fd06 test(calculations): lock pull-path == calculate-path casilla parity for a shared revision (W04.P12.S29)`
