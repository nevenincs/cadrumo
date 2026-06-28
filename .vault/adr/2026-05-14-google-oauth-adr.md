---
tags:
  - '#adr'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-14-google-oauth-reference]]"
  - "[[2026-05-14-google-oauth-research]]"
  - "[[2026-05-13-google-oauth-calc-sheets-adr]]"
  - "[[2026-05-13-google-oauth-twoway-adr]]"
  - "[[2026-05-13-google-oauth-taxonomy-adr]]"
  - "[[2026-05-13-google-oauth-adr]]"
  - "[[2026-05-13-google-oauth-plan]]"
---

# `google-oauth` adr: `schema-to-sheet engine and parity guarantee for bidirectional modelo sheets` | (**status:** `accepted`)

## Problem Statement

The operator stated goal is bidirectional multi-turn round-tripping between Google Sheets and the local AEAT substrate: modelo calculations export to Sheets with live formulas, the operator (or their accountant) edits inputs and possibly cells in the Sheet, the app pulls edits back into the ledger, recomputes locally, and may re-export. The local Python calc engine and the Sheets-evaluated translation MUST yield mathematically identical results for every operator input — anything less invalidates the verification UX (operator looks at the Sheet, sees a wrong number, files an incorrect declaration based on a translation bug).

ADR-6 (calc-sheets) closed the worksheet layout decision but framed the export as read-only; ADR-7 deferred two-way sync entirely. Neither ADR formalises the engine that READS modelo TOML schema and PRODUCES a wired Spreadsheet, nor specifies the parity contract between the two evaluation environments, nor pins the bidirectional pull contract that the user now requires for v1.

This ADR fills those three gaps. It does not redo the per-sheet layout (ADR-6 stands) or the per-domain ledger reverse-merge (ADR-7 + ADR-5 own that surface); it owns the schema-to-sheet engine module, the parity guarantee, and the calc-sheets bidirectional contract that ADR-6's `Entradas` surface now requires.

## Considerations

- Reference audit captured the calc engine surface: single entry point `calculate_registry_snapshot(snapshot, *, inputs, date_context, binding_values, enum_binding_values, relation_values) -> RegistryCalculationResult` at `src/aeat/domain/calculations/registry/_formula_runtime.py:47-128`; pure function over a frozen `RegistrySnapshot`; topological walk via `graphlib.TopologicalSorter`; Decimal context `prec=28 HALF_UP`; three rounding rules (`money-2`, `integer`, `none`). 22-op closed DSL across 24 modelo files. Persisted result is the content-addressed `CalculationRevision` pydantic record.
- Reference audit also surfaced that the parity infrastructure already exists in `src/aeat/domain/calculations/registry/_workbook_parity.py` + `_parity_tapes.py` with `ParityScenario` / `run_parity_scenario` / `replay_parity_tape` plus 5 `corpus/parity_replays/renta_web_open/*.json` externally-sourced fixtures plus a 180-cell parametrisation pattern in `test_modelo_100_autonomic_chain.py:38-58` — reusable as the parity oracle scaffolding for Sheets, not built from scratch.
- Research stream A established that every registry DSL op (`add`, `sum`, `subtract`, `multiply`, `divide`, `percent`, `min`, `max`, `clamp`, `negate`, `copy`, `lookup_parameter`, `lookup_bracket`, `lookup_bracket_by_ccaa`, `previous_period_value`, `previous_period_sum`, `cross_model_sum`, `if_then_else`) has a direct Sheets formula equivalent in closed form. The two `lookup_bracket*` ops need a hidden `_Tariffs` lookup sheet for piecewise-linear bracket schedules — also closed form via `INDEX(_, MATCH(_,_,1))`.
- Research stream A also established the **load-bearing constraint**: Python `Decimal` (arbitrary precision) versus Sheets binary64 (IEEE 754 double) means bit-exact parity at full precision is impossible. The achievable contract is `exact-after-ROUND(value, casilla_scale)` parity per casilla, where `casilla_scale` is the registry-declared rounding rule (2 for `money-2`, 0 for `integer`). This is the only feasible parity standard for a system that mixes Python `Decimal` arithmetic with Sheets-native double-precision evaluation.
- Research stream B established that no first-party precedent exists for this exact contract. QuickBooks Online's "Spreadsheet Sync" (Excel-only, push/pull, last-write-wins) is the closest mental model. Sheetgo / Coupler.io / G-Accon do not publish formal conflict semantics. AEAT itself ships a `dr.xls` workbook for the Renta declaración which is the authoritative parity oracle for Modelo 100; the `workbook_parity_refs` channel in the registry already wires this in.
- Research stream C established the tiered parity oracle pattern: `formulas` (PyPI Python implementation of Excel formulas) for in-process fast tests against the translated formulas; LibreOffice headless for nightly cross-engine evaluation; live Google Sheets `spreadsheets.values.get` with `valueRenderOption=UNFORMATTED_VALUE` for release-gate verification. Each tier catches a different class of translation defect.
- Research stream D established the operational concerns: Drive push notifications are batched at a 3-minute floor (so real-time bidirectional is impossible regardless of design), `batchUpdate` supports optimistic concurrency via `writeControl.targetRevisionId` (enabling write-conflict detection), `values.update` is last-write-wins (so concurrent app + operator writes lose data without explicit synchronisation), and Google Sheets surfaces NO external-modification warning to a live collaborator (so an accountant with the Sheet open does not see the app's re-export — they continue editing stale state).
- The integration is single-operator: a Spanish autónomo plus optionally one accountant. We are NOT building Google Docs-class real-time multi-writer collaboration. Single-writer-at-a-time is acceptable; the operational pattern is "operator/accountant works in the Sheet, then closes the tab, then runs `aeat config google sync calc pull`, then optionally re-exports".

## Constraints

- **Pydantic v2 strict everywhere.** The schema-to-sheet engine consumes the existing `RegistrySnapshot` record (frozen, strict) and emits new pydantic records (frozen, strict, `extra="forbid"`) for every cross-boundary surface: `SheetExportPlan`, `SheetCellAddress`, `SheetFormulaCell`, `SheetValueCell`, `SheetProtectedRange`, `ParityCheckResult`. No dict-shaped intermediate state crosses module boundaries.
- **No partial implementations.** The engine translates EVERY DSL op the registry uses today. No `NotImplementedError` placeholders. New registry ops require an engine extension before they can land in any modelo TOML.
- **No backwards-compat.** No legacy translation paths. No reader for any prior export shape. If the engine version changes the translation strategy, every existing Spreadsheet is regenerated via the idempotent re-export path; no migration shim.
- **Parity is bit-exact-after-per-casilla-rounding.** For every `(modelo, period, inputs)` tuple, every casilla value computed locally MUST equal the Sheets-evaluated value after applying the casilla's declared rounding rule. No tolerance, no fuzziness — `Decimal("123.45") == ROUND(123.4499999, 2) → 123.45` is the contract.
- **Tiered parity oracle stack is mandatory.** A casilla MUST pass all three tiers before the modelo is allowed to flow through the bidirectional pull path. A casilla failing any tier locks the modelo from `sync calc pull` until the translation bug is fixed.
- **Single-writer-at-a-time.** The bidirectional pull contract assumes the operator closed the Sheet before invoking it. The app does not arbitrate concurrent writes; it detects them (via Drive `headRevisionId`) and refuses with a typed error if the Sheet has been modified since the app last wrote.
- **Spanish UX preserved.** Every operator-facing string flows through `tr()` with locale parity across en/es/ca/hu per the project i18n mandate.

## Implementation

### 1. Schema-to-sheet engine — module boundary

New package `src/aeat/application/storage/calc_sheets/` (does not currently exist; referenced as a placeholder in P07 of the L3 plan and now formalised).

The engine consumes:

- A `RegistrySnapshot` (frozen, strict; `aeat.domain.calculations.registry.RegistrySnapshot`).
- A `(modelo, period, year)` triple identifying the target form.
- An `OperatorInputs` mapping (the operator's actual filing inputs, hydrated from `aeat.domain.modelos.ModeloWorkUnit` for the given period).
- A `CalculationRevision` (the canonical locally-computed result; consumed for the `Procedencia` audit sheet).

The engine produces a `SheetExportPlan` pydantic record describing the complete Spreadsheet shape:

- `metadata: SheetExportMetadata` — modelo, period, year, engine_version (SHA of `_formula_runtime.py`), registry_version (SHA of the snapshot), exported_at.
- `entradas: tuple[SheetValueCell, ...]` — input cells, operator-editable, blue conditional-formatted.
- `calculos: tuple[SheetFormulaCell, ...]` — calculation cells with Sheets formulas, green conditional-formatted, app-owned (covered by protected range).
- `resultado: tuple[SheetValueCell, ...]` — output cells (cuota a ingresar / devolver), app-owned.
- `procedencia: tuple[SheetProvenanceRow, ...]` — per-casilla audit metadata (oracle, normativa, app version, registry SHA).
- `guia: SheetGuideContent` — Spanish UX header content.
- `tariffs: tuple[SheetTariffTable, ...]` — hidden `_Tariffs` lookup sheets for `lookup_bracket*` ops.
- `protected_ranges: tuple[SheetProtectedRange, ...]` — addressing every non-`Entradas` range.

The `SheetExportPlan` is a pure data shape. The `apply_export_plan(plan, spreadsheet_id, *, service)` adapter is what calls the real Sheets v4 API to write the plan; the plan itself is testable in isolation.

### 2. Formula translation — closed-form recursion

`translate_expression(expr, *, cell_address_index) -> SheetFormulaExpr` walks the registry expression AST and emits a Sheets formula string. Closed form for all 22 ops:

| Registry op | Sheets translation |
|---|---|
| `add(a, b)` | `=a + b` |
| `sum(values)` | `=SUM(...)` |
| `subtract(a, b)` | `=a - b` |
| `multiply(a, b)` | `=a * b` |
| `divide(a, b)` | `=IFERROR(a / b, 0)` |
| `percent(a, b)` | `=a * b / 100` |
| `min(values)` | `=MIN(...)` |
| `max(values)` | `=MAX(...)` |
| `clamp(value, lo, hi)` | `=MIN(MAX(value, lo), hi)` |
| `negate(a)` | `=-a` |
| `copy(value)` | `=value` |
| `lookup_parameter(key)` | `=VLOOKUP(...)` against a hidden `_Parameters` table |
| `lookup_bracket(value, table)` | `=INDEX(_Tariffs.C:C, MATCH(value, _Tariffs.A:A, 1))` |
| `lookup_bracket_by_ccaa(value, ccaa, table)` | `=INDEX(...)` against per-CCAA bracket subsheet |
| `previous_period_value(modelo, period, casilla)` | Static value + cell-note with provenance path (operator cannot re-evaluate cross-period in Sheet) |
| `previous_period_sum(modelo, periods, casilla)` | Static value + cell-note |
| `cross_model_sum(modelo, period, casilla_set)` | Static value + cell-note |
| `if_then_else(cond, then, else)` | `=IF(cond, then, else)` |
| Per-casilla rounding rule applied at the OUTER expression | `=ROUND(..., scale)` wrapping the whole expression where `casilla.rounding == "money-2"` (scale=2), `"integer"` (scale=0), `"none"` (no ROUND) |

The outer `ROUND` wrap is the load-bearing parity mechanic. Both engines round to the same scale at the same outer boundary, so the per-casilla output is bit-exact across the binary64 / Decimal boundary regardless of intermediate accumulation differences.

### 3. Parity guarantee — three-tier oracle stack

A casilla translation is verified by THREE oracles running on a `ParityScenario` (the existing `_parity_tapes.ParityScenario` record; reused unchanged):

**Tier 1: in-process `formulas` PyPI evaluator.** Fast (~milliseconds per scenario), no network IO, no external process. Catches structural translation bugs (wrong cell reference, wrong op mapping, wrong precedence) deterministically. Runs in `pytest -m unit` on every commit. Module: `src/aeat/application/storage/calc_sheets/_parity_in_process.py` consuming `formulas` from PyPI.

**Tier 2: LibreOffice headless.** Mid-speed (~seconds per scenario), no network IO, requires `soffice` binary in CI image. Catches Sheets-vs-Excel-formula-semantics drift that `formulas` PyPI may have papered over (different `IFERROR` edge cases, different `ROUND` half-up vs banker's-rounding, etc.). Runs in `pytest -m nightly` on a daily schedule. Module: `_parity_libreoffice.py` shells out to `soffice --headless --convert-to csv --infilter="Calc Office Open XML"`.

**Tier 3: live Google Sheets release gate.** Slow (~tens of seconds per scenario), requires real OAuth credentials + Drive folder. The canonical truth: Google's actual server-side formula evaluation. Runs only via `pytest -m live_read` AND `AEAT_LIVE_TESTS_ENABLED=1` AND `aeat_storage_provider_kind=google_drive` — gated behind the same operator-supplied infrastructure as the live OAuth tests. Module: `_parity_live_sheets.py` writes the formula via `values.update`, fetches via `values.get(valueRenderOption=UNFORMATTED_VALUE)`, asserts identity.

A modelo's calc-sheets export path is BLOCKED from operator use until every casilla in its registry passes all three tiers. The block is enforced at `aeat config google sync calc export` invocation time: the command loads a parity-results manifest from `aeat.domain.calculations.parity_manifest` (new namespace) and refuses to export if any casilla shows a tier-failure.

### 4. Bidirectional pull contract — `aeat config google sync calc pull`

The operator workflow is:

1. `aeat config google sync calc export --modelo 100 --period 2025` — initial export. Operator opens the Sheet.
2. Operator (or accountant) edits cells in the `Entradas` sheet. Sheets recomputes the `Cálculos` formulas live; operator sees the updated `Resultado`.
3. Operator closes the Sheet tab. (The single-writer-at-a-time constraint is operator-enforced; the app does NOT block the operator from re-opening the Sheet after step 4.)
4. Operator runs `aeat config google sync calc pull --modelo 100 --period 2025`.
5. App reads the current state of the `Entradas` sheet via `spreadsheets.values.get`, diffs against the last-pushed state recorded in the local `secure_objects_sync_state` table (per ADR-2's sync-state schema), applies the delta as operator-input edits to the local `ModeloWorkUnit`, persists a new `CalculationRevision` if the locally-recomputed values changed.
6. (Optional) Operator runs `aeat config google sync calc export --modelo 100 --period 2025` again to re-write the Sheet from the new authoritative state (per the existing idempotent re-export semantics in ADR-6).

The pull command refuses with `CalcSheetExternallyModifiedError` if the Sheet's Drive `headRevisionId` does not match the last-pushed revision recorded in `secure_objects_sync_state` AND the operator's `Entradas` edits would conflict with an app-side `Cálculos` write that was supposed to land. The conflict path is rare (it requires the operator to have used the Sheet UI to manually edit a protected range AFTER unprotecting it). When it fires, the operator runs `aeat config google sync calc pull --force --resolve {local,remote}` to make an explicit choice.

### 5. Conflict resolution — partition by cell ownership

The `Entradas` sheet is **operator-owned**. App never writes to it except on initial export (and `--force-reset` to wipe operator state). Operator writes are pulled via `sync calc pull`.

The `Cálculos / Resultado / Procedencia / Guía de Lectura / _Tariffs` sheets are **app-owned**. App-side protected ranges declare them un-editable. Operator who explicitly disables protection and edits them creates an app-vs-operator conflict; this is detected at `sync calc pull` time and surfaces as `CalcSheetForeignWriteError` listing the cells the operator edited outside `Entradas`. Operator must explicitly `--resolve` to drop the foreign edits.

This sidesteps Google Sheets' lack of external-modification warnings: each side owns disjoint cells, so concurrent writes touch different cells and don't race. Only the protected-range-disabled path can produce conflicts, and that path requires deliberate operator action.

### 6. Schema-to-sheet engine module surface

The engine is implementation-only; no operator-facing CLI per this ADR. CLI surfaces (`export / pull / list / delete`) live in ADR-6 and the calc-sheets module wires them.

Module layout under `src/aeat/application/storage/calc_sheets/`:

```
_records.py            # SheetExportPlan, SheetCellAddress, SheetFormulaCell, SheetValueCell,
                       # SheetProtectedRange, SheetProvenanceRow, SheetTariffTable,
                       # SheetExportMetadata, ParityCheckResult
_engine.py             # build_export_plan(snapshot, modelo, period, year, inputs, revision) -> SheetExportPlan
_translator.py         # translate_expression(expr, cell_address_index) -> SheetFormulaExpr
_layout.py             # 4-sheet grid layout deriver: casilla -> (row, column) per ADR-6
_parity_in_process.py  # Tier-1 oracle (formulas PyPI)
_parity_libreoffice.py # Tier-2 oracle (soffice headless)
_parity_live_sheets.py # Tier-3 oracle (live Sheets API)
_parity_manifest.py    # Persistence of per-casilla parity-results; gates export at the application layer
_apply.py              # apply_export_plan(plan, spreadsheet_id, service) -> SpreadsheetId; the Sheets v4 adapter
_pull.py               # pull_operator_edits(modelo, period, year, service, state) -> PulledDelta
```

The new ADR also adds:

- `aeat.domain.calculations.parity_manifest` (domain module): `ParityManifest` pydantic record + `ParityManifestRepository` persisting per-casilla tier-pass status. Records consumed by the engine at `export` time to gate.
- Settings field `aeat_calc_sheets_parity_strictness: Literal["all", "tier1_only", "off"]` (default `"all"`) for operator override during development.

### 7. Drive `headRevisionId` write-conflict detection

Every successful `sync calc export` records the Spreadsheet's `headRevisionId` (returned by `files().get(fileId=X, fields="headRevisionId")`) in `secure_objects_sync_state`. Every `sync calc pull` re-fetches the current `headRevisionId` BEFORE reading any cells. If it differs from the last-recorded value, the pull either:

- Recomputes the diff against the last-pushed snapshot (the operator edited the Entradas surface; pull proceeds as designed), OR
- Detects edits outside `Entradas` (the operator unprotected and edited app-owned cells) and refuses with `CalcSheetForeignWriteError` carrying the list of foreign cells.

The `headRevisionId` is a strictly-monotonic Drive-server-generated revision id; using it for conflict detection avoids the unreliability of `modifiedTime` (which can lag by minutes on Google's infrastructure).

### 8. Module-version SHA stamping

Every `SheetExportPlan` records `engine_version` (SHA of `_engine.py` + `_translator.py` + `_layout.py`) and `registry_version` (SHA of the `RegistrySnapshot`). Both stamps land in `Procedencia` AND in the `appProperties` of the Drive file. A `sync calc pull` refuses if `engine_version` on the Sheet doesn't match the current installed app's engine SHA, because a translation-strategy drift across engine versions would invalidate the parity manifest. Operator must re-export under the new engine before pulling.

## Rationale

**A new ADR rather than amending ADR-6 alone.** ADR-6 is the layout decision; the schema-to-sheet engine is the substrate that produces the layout. Putting the engine architecture inside ADR-6 would conflate "what the Sheet looks like" with "what produces the Sheet". The bidirectional contract similarly is a different decision from the layout. Three concerns, three ADRs (ADR-6 for layout, ADR-7 for ledger reverse-merge, this ADR for calc-sheets bidirectional + engine + parity).

**Tier-3 oracle (live Sheets) is mandatory despite cost.** Tiers 1 and 2 are fast but neither IS Google. Sheets evaluates formulas server-side with Google-specific edge cases (different `IFERROR` handling than Excel for certain `#VALUE!` paths, different precedence rules in `*` mixing with `+` under negatives in some 32-bit float corner cases). The only way to assert parity against the system the operator actually uses is to ask the system. Tier-3 runs on a release-gate cadence, not per-commit; it's not in the hot path.

**Partition-by-cell-ownership over operational transforms or last-write-wins.** OT is over-engineered for a single-operator-plus-one-accountant system. LWW silently loses data on concurrent writes. Partition-by-ownership maps every cell to a single writer (operator for Entradas, app for everything else) so concurrent writes touch disjoint cells. The only conflict-edge is operator-disabled protected ranges, which is a deliberate operator action.

**`headRevisionId` over `modifiedTime` for conflict detection.** Drive's `modifiedTime` is approximate (multi-second lag observed in research stream D). `headRevisionId` is strictly monotonic per the Drive API spec and updates synchronously with every write. Conflict detection on `modifiedTime` produces false negatives; on `headRevisionId` is exact.

**`exact-after-per-casilla-ROUND` parity over bit-exact full-precision.** The full-precision contract is mathematically impossible due to `Decimal` vs binary64 representation differences. The rounded contract is achievable and is the only meaningful parity standard for a tax-form calculation surface where the AEAT-canonical outputs are themselves rounded to two decimals (money) or integers (counts).

**Engine SHA stamping for forward compatibility.** When the engine changes the translation strategy (e.g. switching `if_then_else` from `=IF(...)` to `=IFS(...)` for better short-circuit behaviour), every existing exported Spreadsheet becomes ambiguous: is its formula correct under the OLD translation? Under the NEW? Engine SHA stamping refuses the pull until re-export, eliminating ambiguity.

**ADR-7's two-way deferral is superseded by this ADR for the calc-sheets surface specifically.** ADR-7's domain was ledger reverse-merge (transactions, invoices, rental). The bidirectional pull described here is calc-sheets-specific and operationally simpler: only `Entradas` is operator-owned, and the rest is app-owned. ADR-7's broader deferral verdict for ledger surfaces still stands per its own scope.

## Consequences

**Positive.**

- Bidirectional round-trip: operator edits Entradas → app pulls → recomputes → re-exports → operator edits again. Multi-turn workflow supported.
- Parity guarantee is enforceable: a translation bug in any of 22 ops surfaces in Tier-1 within seconds, in Tier-3 within a release cycle. No silent divergence.
- Partition-by-ownership cleanly avoids the concurrent-write trap with no operational transform machinery.
- Engine + registry SHA stamping eliminates "this Sheet was exported under a different engine, results are now meaningless" ambiguity.
- The schema-to-sheet engine is a reusable module: a future Excel exporter or PDF-rendering surface can consume `SheetExportPlan` directly.

**Negative.**

- Tier-3 live testing requires a Drive folder + OAuth credentials in CI; cost is one round-trip to Google per casilla per release-gate run. For Modelo 100's 180 cells across 15 CCAA bracket tables, that's 2700 round-trips per release — affordable, but not free.
- LibreOffice headless adds a CI image dependency; teams running `pytest -m nightly` need `soffice` installed.
- The `_Tariffs` hidden lookup sheet doubles the cell count for modelos that use `lookup_bracket*`. For Modelo 100 this is ~1000 cells added to the Spreadsheet — non-trivial but within Sheets' 10M-cell-per-Spreadsheet limit.
- The parity manifest gate means a translation bug for ONE casilla blocks the WHOLE modelo from operator export. This is conservative but correct: an operator who exports a partial Sheet may file an incomplete declaration.
- Operator workflow requires explicit `sync calc pull` after editing in Sheets; no automatic real-time mirror. Acceptable per the single-operator-plus-one-accountant scope but worth flagging.

**Out of scope (deferred to future ADR amendments).**

- Apps Script-side custom functions for ops that fall outside the closed-form translation set (no such ops exist today; deferred until a registry addition forces the question).
- Sheets-side validation rules (e.g. data-validation drop-downs constraining `Entradas` cells to ranges declared in the registry). Reasonable v2 enhancement; v1 leaves input validation to the local pull step.
- Multi-modelo single-Spreadsheet (one Spreadsheet per filing year covering Modelo 100 + 130 + 303 + ...). v1 keeps one Spreadsheet per (modelo, period) per ADR-6.
- Webhook-driven push notifications (Drive watch + Google Cloud Pub/Sub) for real-time pull triggering. v1 is operator-initiated pull only.

## References

- `[[2026-05-14-google-oauth-reference]]` — calc engine + modelo schema reference audit (codebase-grounded).
- `[[2026-05-14-google-oauth-research]]` — Sheets formula capability + bidirectional sync prior art + parity oracle taxonomy.
- `[[2026-05-13-google-oauth-calc-sheets-adr]]` — ADR-6 worksheet layout (amended in tandem with this ADR to remove the read-only-by-design framing).
- `[[2026-05-13-google-oauth-twoway-adr]]` — ADR-7 ledger reverse-merge (amended to clarify scope boundary: ledger surfaces vs calc-sheets surfaces).
- `[[2026-05-13-google-oauth-taxonomy-adr]]` — ADR-5 per-domain export taxonomy (cross-reference for the registry pull side of bidirectional).
- `[[2026-05-13-google-oauth-plan]]` — google-oauth master plan (updated with new P09 phase covering the engine + parity + bidirectional pull surfaces).
