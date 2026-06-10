---
tags:
  - '#research'
  - '#calculation-aggregation-taxonomy'
date: '2026-06-10'
related: []
---



# `calculation-aggregation-taxonomy` research: `Calculation aggregation mechanism taxonomy: enumeration, overlaps, and the dormant-resolver under-declaration`

Foundational read-only grounding (operator directive 2026-06-10) for a BINDING ADR that
codifies the canonical calculation-aggregation mechanism per calculation type. Trigger: a
single fold-in (M100 casilla 0604 ← sum of M130 casilla 19 over 1T-4T) is expressible BOTH
as a `relation` and as a `previous_filing` binding — the engine has multiple overlapping
aggregation mechanisms and which is canonical for which scenario is implicit, a mission
risk for calculation correctness. All claims anchored at HEAD; honest gaps flagged.

## Findings

### The single engine seam

Every mechanism ultimately feeds one function: `calculate_registry_snapshot(snapshot, *,
inputs, binding_values, enum_binding_values, relation_values, date_binding_values, ...)`
(`domain/calculations/registry/_formula_runtime.py:173`). The engine's value channels are
`inputs`, `binding_values`, `enum_binding_values`, `relation_values`, `date_binding_values`.
Every aggregation mechanism is a strategy for POPULATING one channel before the engine runs.
The live calculate entrypoint is
`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
(`application/modelo/_calculation_actions.py:419`); the CLI is pinned to it. The
AUTHORITATIVE live source mesh is the `merge_source_resolutions((...))` tuple at
`_calculation_actions.py:516-534`.

### The six mechanisms + live-mesh enrollment

| # | Mechanism | owned_source | Scenario | Live-calculate enrollment |
|---|---|---|---|---|
| 1 | Relation / `cross_model_output` (`RelationPrefillSourceResolver`, `_relation_prefill.py:250`) | `relation_prefill` | cross-modelo annual fold-in | **DORMANT — not in the mesh tuple**; only the Google-Sheets workbook path + isolated tests call it |
| 2 | `previous_filing` binding (`PreviousFilingSourceResolver`, `_multi_year.py:443`; selector `_bindings_previous_filing.py:187`) | `previous_filing` | cross-period / cross-modelo carry | **ENROLLED** (`_calculation_actions.py:530`, wrapped by the D3 303-exclusion) |
| 3 | Ledger aggregation (`LedgerIva/RentaExpense/RentaIncome/OssIoss`, `_modelo_bindings.py:142+`) | `ledger_*_aggregation` | transactions → same-period casillas | **PARTIAL**: Iva + RentaExpense enrolled; **RentaIncome + OSS DORMANT** |
| 4 | Formula / casilla formulas (`_formula_runtime.py:173`) | (engine core) | intra-revision derivation | **ALWAYS runs** — terminal step every mechanism feeds |
| 5 | IVA-wallet compensación decision (`IvaWalletDecisionSourceResolver`, `_iva_wallet_reconciliation.py:61`) | `iva_wallet_decision` | M303 casilla 110 carry (adjudicated) | **ENROLLED** via a dedicated pre-mesh gate (`_iva_wallet_gate.py:161`) |
| 6 | Other channels: `profile`, `borrador` (M100), operator `--casilla`/`--binding` overrides, declaration-period inputs (`_binding_resolution.py`) | `profile`/`borrador`/… | facts / prefill / overrides | **ENROLLED** (pre-mesh) |

### THE HEADLINE RISK — dormant relation resolver = latent under-declaration

`RelationPrefillSourceResolver` drives every `cross_model_output` fold-in — M100←M130,
M200, and the M180/M190/M193/M111/M115/M123 reconciliations — but it is NOT in the live mesh
tuple (`_calculation_actions.py:516-534`). Its only non-test caller is the Google-Sheets
workbook calc-sync (`_config/_google_sync_calc.py:125`), a different surface. So these
fold-ins are GREEN ONLY in isolated continuity tests that call `resolve_relations_from_local_store`
directly; the LIVE operator `calculate` path never fires them and emits `value=None` → a
blank casilla (`_relation_prefill.py:157`). Worse, `collect_unhandled_source_diagnostics`
(`_source_mesh.py:242-268`) — which would flag a binding/relation with no resolver — has NO
caller on the live calculate path, so the blank surfaces NO advisory. This is a latent
under-declaration: the M100 annual fold-in (and M200, and the reconciliations) silently do
not happen in real calculate today.

Additionally DORMANT: `LedgerRentaIncomeAggregationSourceResolver`, `OssIossLedgerSourceResolver`,
and ≥8 declared binding source-kinds with NO enrolled resolver at all (`withholding` 13,
`related_party_operation` 6, `foreign_asset` 6, `refund_operation` 5, `ledger_oss_aggregation`
5, `atribucion_member` 4, `ledger_renta_income_aggregation` 3, `collectible_invoice` 17 — counts
from the registry TOMLs). (HONEST GAP: whether some are served by a separate non-calculate
`aggregate_per_modelo` surface was not fully traced.)

### Overlap matrix (same aggregation, ≥2 mechanisms)

- **Cross-modelo annual fold-in (the trigger):** Relation `cross_model_output` op=sum vs
  `previous_filing` binding op=sum. M100←M130 as a relation
  (`100/.../relations/0007-...toml`) vs M390←M303 as a binding
  (`390/.../bindings/0001-bindings.toml:70`) — IDENTICAL shape (`source_periods=[1T..4T],
  op=sum`), two entities, two resolvers, DIFFERENT live-fire status (M390's binding fires;
  M100's relation does not). The codebase's own docstrings (`_relations.py:1`,
  `_binding_prefill.py:7-13`) acknowledge the dual modelling.
- **M303 casilla 110 compensación:** `previous_filing` vs `iva_wallet_decision` — ALREADY
  adjudicated by explicit exclusion (`_previous_filing_resolution_excluding_iva_compensation`,
  `_calculation_actions.py:603-630`, ADR ruling D3).
- **Relation `target_binding` dual-write:** a relation with `target_binding` materialises
  BOTH a relation_value and a binding_value (`_relations.py:198-231`); the conflict guard
  catches intra-relation conflicts but NOT a relation-vs-previous_filing collision on the
  same binding id (honest gap).

### Proposed canonical taxonomy (PROPOSAL for the ADR to ratify)

- Intra-revision derivation → **Formula** (uncontested; sole terminal step).
- Ledger projection (transactions → same-period casillas) → **Ledger resolver** (owns
  transaction provenance + source_transaction_ids + no-silent advisory).
- Cross-period same-modelo carry → **previous_filing binding** (selector models year/period
  offset; enrolled; D2 override rule adjudicates conflicts).
- **Cross-modelo fold-in → NEEDS RATIFICATION:** relation vs previous_filing. Registry
  currently splits (relations for M100/M200/M180/190/193; previous_filing for M390/M353).
  Option A = canonicalise on `relation` + ENROLL `RelationPrefillSourceResolver` in the live
  mesh (preserves the larger relation corpus, fixes the dormancy); Option B = canonicalise on
  `previous_filing` (already enrolled, no mesh change, fewer dormant resolvers) + migrate the
  relation fold-ins. The ADR MUST pick one and migrate the minority. Either way the dormant-
  resolver under-declaration must be closed.
- IVA compensación → **iva_wallet_decision** (already canonical by D3; adds wallet-evidence
  reconciliation a raw fold cannot).
- Profile facts → **profile binding**; Borrador prefill (M100) → **borrador binding**.

### Risks the ADR must address

1. Dormant relation resolver = latent under-declaration (headline; close it whichever option wins).
2. Same aggregation, two unrelated code paths with different live-fire status (M100 relation vs M390 binding).
3. `relation.target_binding` cross-mechanism dual-write has no collision guard.
4. 3+ dormant resolvers + ≥8 resolver-less source-kinds also fail silently to blank; `collect_unhandled_source_diagnostics` is defined but never called on the live path — wire it.
5. Mechanism precedence is implicit (D2/D3 live as inline comments, not a declared precedence table) — codify it.

Key files for the ADR: `_calculation_actions.py:419-580` (live mesh), `_relation_prefill.py`,
`_multi_year.py:443` + `_bindings_previous_filing.py`, `_modelo_bindings.py:142+`,
`_formula_runtime.py:173`, `_iva_wallet_gate.py:72-173`, `_binding_resolution.py`,
`_relations.py:198-231`, `_source_mesh.py:242-268`.
