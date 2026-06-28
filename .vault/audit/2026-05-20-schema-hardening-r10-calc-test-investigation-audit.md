---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# schema-hardening R10 — calculation-registry test failure investigation

Ten tests in `src/aeat/domain/calculations/registry/` fail. All touch modelos 123, 130, 131. This document records the assertion that fails, the verdict (stale test vs registry/engine bug), the introducing commit, and the recommended fix for each failure.

---

## Failure 1 — `test_committed_modelo_130_registry_snapshot_is_calculable`

**File:** `src/aeat/domain/calculations/registry/test_committed_registry.py:46`

**Assertion that fails:**
```python
assert {entry.target for entry in result.entries} == {"03", "04", "07", "09", "11", "12", "13", "14", "17", "19"}
```

**Actual left set includes:** `"saldo-negativo-fin-periodo"` (one extra item)

**Verdict: STALE TEST** — registry is correct.

Commit `eb4306024` (2026-05-15) added `saldo-negativo-fin-periodo` as a `computed` casilla to M130/2019-y-siguientes with formula `modelo-130-saldo-negativo-fin-periodo = max(0, -casilla17)`. The calculation engine now emits this entry because it is a computed casilla declared in the snapshot. The test assertion was written in commit `afb0f390f` (2026-05-04) before the carry-forward feature existed. No test was updated when `eb4306024` landed.

**Introducing commit:** `eb4306024` — "Modelo 130 + 131 prior-quarter negative-result carry-forward"

**Recommended fix:** Add `"saldo-negativo-fin-periodo"` to the expected set:
```python
assert {entry.target for entry in result.entries} == {
    "03", "04", "07", "09", "11", "12", "13", "14", "17", "19",
    "saldo-negativo-fin-periodo",
}
```

---

## Failures 2–6 — `test_committed_modelo_131_registry_snapshot_calculates_objective_estimation_totals` (5 parametrized cases)

**File:** `src/aeat/domain/calculations/registry/test_committed_registry.py:204`

**Assertion that fails (all 5 parameter variants):**
```python
assert set(entries) == {"04", "06", "07", "10", "13", "15"}
```

**Actual left set includes:** `"saldo-negativo-fin-periodo"` in every revision (2019-2023, 2024, 2025, 2026).

**Verdict: STALE TEST** — registry is correct.

Commit `eb4306024` (2026-05-15) added `saldo-negativo-fin-periodo` as a `computed` casilla to all four M131 revisions (2019-2023, 2024, 2025, 2026), same pattern as M130. The test was written in commit `3dfd17a39` (2026-05-05) and never updated when the carry-forward feature landed.

**Introducing commit:** `eb4306024` — "Modelo 130 + 131 prior-quarter negative-result carry-forward"

**Recommended fix:** Add `"saldo-negativo-fin-periodo"` to the expected set in all 5 parametrized cases:
```python
assert set(entries) == {"04", "06", "07", "10", "13", "15", "saldo-negativo-fin-periodo"}
```

---

## Failure 7 — `test_committed_modelo_123_registry_snapshot_uses_2019_2023_shape`

**File:** `src/aeat/domain/calculations/registry/test_committed_registry.py:140`

**Assertion that fails:**
```python
result = calculate_registry_snapshot(
    snapshot,
    inputs={
        "01": ..., "02": ..., "03": ..., "04": ..., "05": ..., "07": ...,
    },
    ...
)
```

**Error:** `RegistryValidationError: unknown registry input casilla ids: ['01', '02', '03', '04', '05', '07']`

The secondary assertion at line 154-163 would also fail:
```python
assert tuple(casilla.id for casilla in snapshot.revision.casillas) == (
    "01", "02", "03", "04", "05", "06", "07", "08",
)
```

**Verdict: STALE TEST** — registry is correct.

Commit `5bce78507` (2026-05-19) fragmented the M123 registry by moving the 2019-2023 revision into its own file. During fragmentation the casilla IDs in the 2019-2023 revision were renamed from bare numerics (`"01"` through `"08"`) to the `-legacy` scheme (`"01-legacy"` through `"08-legacy"`) to distinguish them from the 2024-y-siguientes IDs that share the same number space. The test was last modified in commit `fff3eac4c` (2026-05-18), the day before the fragmentation, and was never updated to reflect the new ID scheme.

**Introducing commit:** `5bce78507` — "Fragment modelo 123 registry"

**Recommended fix:** The test inputs and casilla-id assertion must use the `-legacy` suffix IDs. Map:
- inputs: `"01"` → `"01-legacy"`, `"02"` → `"02-legacy"`, etc.
- casilla sequence assertion: `("01", "02", ..., "08")` → `("01-legacy", ..., "08-legacy")`
- The `{entry.target for entry in result.entries} == {"06", "08"}` must become `{"06-legacy", "08-legacy"}` if those are the computed output targets.

Verify the actual computed targets in `2019-2023/revision.toml` before updating the set.

---

## Failure 8 — `test_cross_model_relations_resolve_from_observations_for_revision_edge_years`

**File:** `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py:80`

**Assertion that fails:**
```python
resolved = resolve_relation_values_from_observations(
    revision, observations, filing_year=filing_year, period=period
)
```

**Error:** `RegistryValidationError: relation requirement ('modelo-130-rel-self-prior-quarter-negative',) copy aggregation requires one observation`

**Verdict: REGISTRY BUG** — the `relation_source_requirements` function at `_relations.py:67-68` returns static `source_periods` for any target period:
```python
source_periods = relation.source_periods or (period,)
```
For M130's relation, `source_periods = ("1T", "2T", "3T")` regardless of the current target period. With `aggregation = copy`, the caller expects exactly one period. A `copy` relation that nominates three source periods is structurally incoherent — copy means "take the value from exactly one prior filing". The registry declares `period_alignment = { mode = "previous_quarter" }` but there is no code path that uses `period_alignment` to dynamically resolve source period from target period; that mechanism was never implemented. The relation should instead use `source_period_offset_from_target = -1` (one quarter back), which has a working implementation in `_derive_offset_source_anchor`.

**Introducing commit:** `eb4306024` — "Modelo 130 + 131 prior-quarter negative-result carry-forward" (introduced both the static `source_periods = ["1T","2T","3T"]` + `aggregation = copy` mismatch and the unimplemented `period_alignment` field)

**Recommended fix (registry change):** In `130.toml` and all four `131/revisions/*.toml` files, replace:
```toml
source_periods = ["1T", "2T", "3T"]
target_periods = ["2T", "3T", "4T"]
aggregation = { op = "copy" }
period_alignment = { mode = "previous_quarter" }
```
with:
```toml
source_period_offset_from_target = -1
target_periods = ["2T", "3T", "4T"]
aggregation = { op = "copy" }
```
Remove the `source_periods` and `period_alignment` keys. `source_period_offset_from_target = -1` uses the already-implemented quarterly ordinal shift (`_derive_offset_source_anchor`) which correctly maps target `2T` → source `1T`, `3T` → `2T`, `4T` → `3T`.

---

## Failure 9 — `test_cross_dependency_roles_match_supported_modelo_hierarchy`

**File:** `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py:83`

**Assertion that fails:**
```python
assert relation.source_modelo != modelo.id, f"{modelo.id}/{revision.id}/{relation.id}"
```

**Actual failure:** `130/2019-y-siguientes/modelo-130-rel-self-prior-quarter-negative` — `relation.source_modelo == "130" == modelo.id`

**Verdict: REGISTRY BUG** (same root cause as Failure 8, but the test is exposing a separate constraint violation).

The contract test asserts that a cross-model relation must reference a *different* modelo — self-referencing "previous_period" relations where a modelo reads its own prior-quarter output are a conceptually distinct mechanism from true cross-model dependencies. The carry-forward design in `eb4306024` modelled intra-modelo carry-forward using the same `RelationDefinition` schema as cross-model relations, which violates the explicit contract that `relation.source_modelo != modelo.id`. M131 has the same issue across all four revisions (only M130 is reported because the test stops at the first failure).

**Introducing commit:** `eb4306024` — "Modelo 130 + 131 prior-quarter negative-result carry-forward"

**Recommended fix:** Two options:

*Option A (preferred) — make the test aware of the intra-modelo pattern:*
The test should permit `source_modelo == modelo.id` when `relation.kind == "previous_period"`, which is the intended discriminator for "same-modelo prior-quarter" carry-forward. Update the assertion to:
```python
if relation.kind != "previous_period":
    assert relation.source_modelo != modelo.id, ...
```

*Option B — restructure the registry:*
Remove the `relations` entry for intra-modelo carry-forward and instead model it purely as a `binding` with `source = "previous_filing"` (which already works for the `modelo-130-resultados-negativos-anteriores` binding). This would eliminate the relation entirely, fixing both Failures 8 and 9, and the `source_periodo` mismatch becomes irrelevant.

Option B is architecturally cleaner but requires verifying that `test_formula_bearing_revisions_consume_calculation_relations` (Failure 10) and the roundtrip test suite still pass after removal.

---

## Failure 10 — `test_formula_bearing_revisions_consume_calculation_relations`

**File:** `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py:179`

**Assertion that fails:**
```python
assert required.issubset(consumed), f"{modelo.id}/{revision.id}: {sorted(required - consumed)}"
```

**Actual:** `130/2019-y-siguientes: ['modelo-130-rel-self-prior-quarter-negative']`

**Verdict: REGISTRY BUG** (again same root cause — `eb4306024` placed an intra-modelo carry-forward relation under `dependency_role = "direct_calculation"` but no formula expression references the relation ID).

`_formula_relation_refs` collects relation IDs from formula expressions (nodes of the form `{ relation = "..." }`). `_algorithm_relation_refs` collects relation IDs from algorithm binding inputs. Neither fires for `modelo-130-rel-self-prior-quarter-negative` because the carry-forward value reaches casilla 15 through the `binding` mechanism (`modelo-130-resultados-negativos-anteriores`), not through a formula expression that explicitly references the relation. The relation appears in `dependency_classifications.relation_refs` only, which is not checked by the test.

**Introducing commit:** `eb4306024`

**Recommended fix:** Depends on the choice made for Failure 9:

- If Option A (keep relation, fix hierarchy test): also change `dependency_role = "direct_calculation"` to a new role such as `"intra_modelo_carry_forward"` that is not in `_CALCULATION_ROLES`, so the consumption test does not require formula-expression coverage for it. Alternatively, keep `dependency_role = "direct_calculation"` but update `_formula_relation_refs` to also inspect bindings that declare `target_binding` when those bindings are backed by a relation.

- If Option B (remove relation, use binding-only): this failure disappears automatically since the relation ID no longer exists.

---

## Common root cause

All ten failures share a single root cause: commit `eb4306024` ("Modelo 130 + 131 prior-quarter negative-result carry-forward", 2026-05-15) introduced intra-modelo carry-forward by reusing the cross-model `RelationDefinition` schema for a "same-modelo prior-quarter" read. This created three structural mismatches that the existing contract test suite was designed to catch:

1. **`saldo-negativo-fin-periodo` computation output now appears in `result.entries`** — tests that asserted the exact set of computed targets were not updated (Failures 1–6).

2. **`source_periodo` + `copy` aggregation mismatch** — the relation declares three static `source_periods` but `copy` semantics require exactly one. The `period_alignment` field was introduced as metadata but has no code implementation; `source_period_offset_from_target` is the working mechanism (Failure 8).

3. **`source_modelo == modelo.id` violates the cross-model hierarchy contract** — the test correctly enforces that relations point to *other* modelos (Failure 9) and that calculation-role relations are consumed by formulas (Failure 10).

The M123 failure (Failure 7) has a separate but related root cause: commit `5bce78507` ("Fragment modelo 123 registry", 2026-05-19) renamed the 2019-2023 casilla IDs to `*-legacy` without updating the test that was written two days earlier.

---

## Recommended fix order

1. **Fix M123 stale test first** (Failure 7) — purely a test update, no production-code risk, isolated to one revision. Update casilla IDs to `-legacy` suffix and verify the computed-target set.

2. **Fix M130/M131 result.entries assertions** (Failures 1–6) — add `"saldo-negativo-fin-periodo"` to the expected sets. These are straightforward test updates with zero production-code change.

3. **Decide Option A vs Option B for the registry structural bug** (Failures 8, 9, 10) — the three failures are locked together:
   - Option A path: (a) replace `source_periods`/`period_alignment` with `source_period_offset_from_target = -1` in M130 and all four M131 revisions; (b) update the hierarchy-contract test to permit `kind == "previous_period"` self-references; (c) change `dependency_role` from `"direct_calculation"` to an intra-modelo role excluded from `_CALCULATION_ROLES`, or update the formula-consumption checker to trace binding-backed relation paths.
   - Option B path: remove the `relations` entries entirely from M130 and M131 for the carry-forward; the `previous_filing` binding already provides the value for casilla 15 without needing a formal relation. Confirm with a targeted test that the binding resolver correctly materialises `modelo-130-resultados-negativos-anteriores`.

Option B is the lower-risk path: fewer moving parts, no new role vocabulary, and the production execution path already works through the binding (the failing tests are contract-validation gates, not execution failures for the common 1T case). Confirm the binding-only approach covers 2T/3T/4T filings correctly before committing.
