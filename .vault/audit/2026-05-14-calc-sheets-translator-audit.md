---
tags:
  - '#audit'
  - '#calc-sheets-translator'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-14-google-oauth-adr]]"
  - "[[2026-05-13-google-oauth-plan]]"
---

# `calc-sheets-translator` audit: schema-to-sheet translator per-modelo coverage

## Scope

Sweeps every AEAT modelo registered under `registry/aeat/modelos/` and
attempts to assemble a `SheetExportPlan` for its active revision. For
each modelo the audit:

1. Resolves a representative period that matches the revision's
   declared `period_selector` (e.g. `1T` for quarterly, `0A` for
   annual, `AD-HOC` for ad-hoc, `1P` for modelo 202 pago fraccionado,
   `alta` for modelo 036 census).
2. Walks every `FormulaExpression` AST attached to every casilla in
   the revision and tallies the registry ops and leaf types used.
3. Cross-references the tally against the closed-form translator's
   supported-op set and supported-leaf set.
4. Records, per modelo: `(casilla_count, formula_count,
   translatable_formula_count, blocked_formula_count, ast_node_count,
   blocker_set)`.

The audit is executed end-to-end from a real `RegistryValidator` run
on the working tree's `registry/aeat/` corpus, so the verdict reflects
the registry as it ships today, not a synthetic subset.

## Findings

### Verdict by modelo

| Modelo | Cadence       | Period | Casillas | Formulas | Translatable | Blocked | Status        |
|--------|---------------|--------|---------:|---------:|-------------:|--------:|---------------|
| 036    | ad_hoc        | alta   |        2 |        0 |            0 |       0 | NO_FORMULAS   |
| 100    | annual        | 0A     |     2235 |      168 |          163 |       5 | NEAR_COMPLETE |
| 111    | profile_based | 1T     |       30 |        2 |            2 |       0 | OK            |
| 115    | quarterly     | 1T     |        5 |        2 |            2 |       0 | OK            |
| 123    | quarterly     | 1T     |       14 |        5 |            5 |       0 | OK            |
| 130    | quarterly     | 1T     |       19 |       10 |           10 |       0 | OK            |
| 131    | quarterly     | 1T     |       15 |        6 |            6 |       0 | OK            |
| 180    | annual        | 0A     |       30 |        3 |            0 |       3 | BLOCKED       |
| 184    | annual        | 0A     |        6 |        0 |            0 |       0 | NO_FORMULAS   |
| 190    | annual        | 0A     |        3 |        3 |            0 |       3 | BLOCKED       |
| 193    | annual        | 0A     |        3 |        3 |            0 |       3 | BLOCKED       |
| 200    | annual        | 0A     |     3215 |        1 |            0 |       1 | BLOCKED       |
| 202    | quarterly     | 1P     |       50 |       13 |           13 |       0 | OK            |
| 232    | annual        | 0A     |        3 |        0 |            0 |       0 | NO_FORMULAS   |
| 303    | quarterly     | 1T     |       10 |        3 |            3 |       0 | OK            |
| 308    | ad_hoc        | AD-HOC |        2 |        0 |            0 |       0 | NO_FORMULAS   |
| 309    | ad_hoc        | AD-HOC |        5 |        1 |            1 |       0 | OK            |
| 322    | monthly       | 01     |       10 |        3 |            3 |       0 | OK            |
| 347    | annual        | 0A     |        2 |        0 |            0 |       0 | NO_FORMULAS   |
| 349    | profile_based | 1T     |       13 |        0 |            0 |       0 | NO_FORMULAS   |
| 353    | monthly       | 01     |       10 |        3 |            3 |       0 | OK            |
| 360    | ad_hoc        | AD-HOC |        2 |        0 |            0 |       0 | NO_FORMULAS   |
| 369    | ad_hoc        | 1T     |        6 |        1 |            1 |       0 | OK            |
| 390    | annual        | 0A     |       13 |        3 |            3 |       0 | OK            |
| 720    | annual        | 0A     |        2 |        0 |            0 |       0 | NO_FORMULAS   |
| 840    | ad_hoc        | 0A     |        2 |        0 |            0 |       0 | NO_FORMULAS   |

### Status taxonomy

- **OK (12 modelos)**: every formula in the revision translates to a
  closed-form Sheets expression. The engine emits a complete workbook
  today. Modelos: 111, 115, 123, 130, 131, 202, 303, 309, 322, 353,
  369, 390.
- **NEAR_COMPLETE (1 modelo)**: 163 / 168 formulas translate; 5 are
  blocked on bracket lookups. Modelo: 100.
- **BLOCKED (4 modelos)**: every computed formula in the revision is
  blocked on the same op or leaf class. Modelos: 180, 190, 193, 200.
- **NO_FORMULAS (9 modelos)**: census or informative declarations with
  zero computed casillas. The engine produces a value-cell-only
  workbook (Entradas + Procedencia + Guía). Modelos: 036, 184, 232,
  308, 347, 349, 360, 720, 840.

### Global op + leaf frequency

The translator supports the ops listed in `_SUPPORTED_OPS`. Across
every formula AST in every revision:

| Op / leaf                  | Count | Supported? |
|----------------------------|------:|------------|
| negate                     |   120 | yes        |
| sum                        |   100 | yes        |
| subtract                   |    68 | yes        |
| percent                    |    18 | yes        |
| add                        |    18 | yes        |
| copy                       |    17 | yes        |
| max                        |    17 | yes        |
| min                        |    11 | yes        |
| if_then_else               |     9 | yes        |
| greater_than               |     4 | yes        |
| divide                     |     4 | yes        |
| multiply                   |     4 | yes        |
| less_equal                 |     4 | yes        |
| equal                      |     1 | yes        |
| **lookup_bracket**         |     2 | **NO**     |
| **lookup_bracket_by_ccaa** |     2 | **NO**     |
| leaf: casilla              |   705 | yes        |
| leaf: literal              |    53 | yes        |
| leaf: parameter            |     9 | yes        |
| leaf: binding              |     7 | yes        |
| **leaf: relation**         |    28 | **NO**     |
| **leaf: dispatch_table**   |     2 | **NO**     |

### Coverage statistics

- 17 / 26 modelos are fully translatable today (including
  no-formula informative shells). 65 % of the surface.
- 12 / 26 modelos have computed formulas AND translate completely.
- 1 modelo (100) is at 97 % per-formula coverage.
- The 4 BLOCKED modelos share a single root cause: they aggregate
  values from other modelos through cross-revision `relation` leaves
  that no parameter mirror exists for.

### Op gap: `lookup_bracket` and `lookup_bracket_by_ccaa`

- Both ops surface only in modelo 100 (IRPF Renta annual). Two
  occurrences each; both consume a `bracket_table` parameter
  declared in the revision's `parameters` table.
- `lookup_bracket` resolves a piecewise-linear cuota from
  `(lower_bound, upper_bound, fixed_addition, marginal_rate)` rows.
  The `Tarifas` tab already mirrors bracket-table parameters with one
  row per bracket (the engine's existing `SheetTariffTable` record
  with `data_type="bracket_table"`). The Sheets closed form is:

      cuota = fixed_addition + marginal_rate * (base - lower_bound)

  resolved by `MATCH(base, lower_bound_column, 1)` against the bracket
  rows. The translator must emit an `INDEX(...) + INDEX(...) *
  (base - INDEX(...))` triple over the existing tariff anchor range.
- `lookup_bracket_by_ccaa` is a CCAA-dispatched bracket lookup. It
  takes a CCAA binding (e.g. `profile.ccaa`) and a `dispatch_table`
  leaf mapping each CCAA code to a `bracket_table` parameter id.
  Sheets cannot resolve a dispatch table at parse time, so the
  closed form must materialise one `lookup_bracket` per CCAA branch
  and route through `SWITCH('Entradas'!binding_cell, "ES-MD",
  bracket_lookup_madrid, "ES-CT", bracket_lookup_cataluna, …,
  default_bracket_lookup)`. That requires the layout planner to
  allocate a separate `Tarifas` region per dispatched bracket table.

### Leaf gap: `relation`

- 28 relation references across modelos 180, 190, 193, 200.
- Every relation rolls up values from a different modelo and a
  different filing period (e.g. `modelo-190-rel-111-trabajo-
  dinerario-percepciones-anual` aggregates the four `modelo 111`
  quarterly perceptions of a calendar year into the annual modelo
  190 declaration).
- Two surface options:
  1. **Mirror relations as `Tarifas` rows.** Pre-resolve the
     relation value on the local side via
     `resolve_relation_values_from_observations`, then write it as a
     scalar value in `Tarifas`. The translator already knows how to
     compile a leaf into a `'Tarifas'!Xn` reference. Lowest-cost
     option but loses bidirectional auditability of the underlying
     observations.
  2. **Sibling-spreadsheet `IMPORTRANGE`.** Each related modelo's
     spreadsheet provides the per-period values; the rolling-up
     modelo's `Cálculos` cells reference them via Sheets
     `IMPORTRANGE`. Bidirectional but operationally fragile (every
     `IMPORTRANGE` triggers an explicit access grant on the
     operator's browser, and Drive scope `drive.file` does not
     reach `IMPORTRANGE` targets without an interactive consent).
- Option 1 is the pragmatic shipping path; option 2 is reserved for
  if the operator demands per-perceptor drill-down.

### Leaf gap: `dispatch_table`

Only meaningful inside `lookup_bracket_by_ccaa`. Resolves alongside
that op (see above).

### Snapshot-build hygiene (not a translator issue)

The first run of this audit reported 5 modelos as "snapshot fail":
036, 202, 308, 309, 360. Re-running with the modelos' declared
period codes (`alta`, `1P`, `AD-HOC`) confirmed every revision builds
and every formula in those revisions translates. The original
failure was the audit harness's period candidate list, not the
registry or the engine. Future audit runs should source period
candidates from each revision's `period_selector` instead of using a
fixed list.

## Recommendations

### S1 — ship modelo 100 bracket-lookup support

- Extend `_translator._translate` with `lookup_bracket` and
  `lookup_bracket_by_ccaa` handlers that emit the closed-form
  `INDEX(...) + INDEX(...) * (base - INDEX(...))` triple over the
  existing `Tarifas` bracket rows.
- Add a `SWITCH`-based dispatch wrapper for the CCAA op. The layout
  planner already enumerates `dispatch_table` parameter targets via
  `_walk_expression_parameters`, so each branch's `bracket_table` is
  already mirrored — the translator just needs to resolve the
  per-CCAA region anchors.
- This single change moves modelo 100 from NEAR_COMPLETE (97 %) to
  OK (100 %) and is the only blocker for a real Renta filing
  surface.

### S2 — resolve relation leaves through `Tarifas` mirroring

- Treat a `relation` leaf the same way the layout planner treats a
  parameter: reserve a scalar cell in `Tarifas`, anchor it through
  `parameter_cells`-style mapping (rename to "external value
  cells"), and resolve the leaf to that anchor.
- Pre-populate the cell value by invoking
  `resolve_relation_values_from_observations` against the caller-
  supplied previous-period observation set, so the workbook ships
  with the rolled-up value already written. The pull adapter then
  treats the cell as protected (a `Tarifas` row, not an `Entradas`
  row), so the operator can audit it but not silently overwrite it.
- This unblocks modelos 180, 190, 193, 200 — every annual
  retentions / capital / payment-fraccionado roll-up.

### S3 — make the audit harness self-driving on `period_selector`

- The current audit harness uses a hand-curated period candidate
  list. Replace with a per-modelo lookup against
  `revision.period_selector.periods` so the audit runs across every
  declared period without manual maintenance.

### S4 — register the gap in the engine's `TranslationError` surface

- The current translator raises `TranslationError` with `op=...` and
  a free-text hint. The CLI `export` command catches this and
  surfaces a generic "translator gap" error. Operators who try to
  export modelo 100 today should see a typed `CalcSheetsCoverageError`
  pointing at this audit's recommendations (S1 / S2) so they know
  which modelos are deferred and which work today.

## Audit harness

The numbers in this audit were captured by an AST walk over every
revision of every modelo. The harness is reproducible by loading
the registry tree, iterating `modelos`, calling `build_snapshot`
with `period_selector`-aware period candidates, and walking every
`FormulaExpression` recursively into per-op and per-leaf counters.
The translator's supported-op surface is the
`_SUPPORTED_OPS` frozenset declared in the translator module.

## Follow-up — verification after S1 + S2 landed

A second pass of the audit harness, with period candidates sourced
from each revision's `period_selector.periods` (S3 from the
recommendations above also applied as part of the audit-harness
itself) reports the following:

| Status         | Count | Modelos                                                                                                            |
|----------------|------:|--------------------------------------------------------------------------------------------------------------------|
| OK             |    17 | 100, 111, 115, 123, 130, 131, 180, 190, 193, 200, 202, 303, 309, 322, 353, 369, 390                                |
| NO_FORMULAS    |     9 | 036, 184, 232, 308, 347, 349, 360, 720, 840                                                                        |
| TRANSLATOR_GAP |     0 | -                                                                                                                  |
| SNAPSHOT_FAIL  |     0 | -                                                                                                                  |

Every modelo with at least one formula now translates to a complete
closed-form Sheets expression. Modelo 100 (Renta annual, 168
formulas including the IRPF state + autonomic bracket cuotas) moved
from 97 % to 100 % per-formula coverage; modelos 180 / 190 / 193 /
200 (annual roll-ups of quarterly retentions / capital / pago
fraccionado) moved from 0 % to 100 %.

### Live parity proofs

Two end-to-end live exports executed against the operator's Drive
after S1 + S2 landed:

- **Modelo 100, state IRPF cuota on Base Liquidable General**
  (formula `renta-2025-cuota-escala-estatal-sobre-base-liquidable-
  general`). Casilla 0505 set to 50000 in the workbook's `Entradas`
  tab. The Sheets `INDEX(...) + INDEX(...) * (base - INDEX(...))`
  bracket expansion returns `7100.75` for casilla 0528; the local
  Decimal runtime returns `Decimal("7100.75")`. Bit-exact agreement.
- **Modelo 190, annual perceptor roll-up** (formulas 136-144,
  145-160, 161-175). Nineteen relation values written into the
  `Tarifas` tab as test counts 1..9 / importes 100..900 / retencion
  1234.56. The Sheets `SUM` formulas return 45 / 4500 / 1234.56 in
  the three computed casillas; identical to the local roll-up of
  the same nineteen scalars. Bit-exact agreement.

### Engine version stamp

The engine version remains `calc-sheets/0.1.0`. The follow-on work
that landed S1 and S2 stays in-band with the existing apply-adapter
contract: workbooks created against the prior engine version stamp
are overwritten on next export and acquire the new
`bracket_ranges` + `relation_cells` regions in `Tarifas`. No
backwards-compat shim is needed — workbooks are derivable from the
registry, and registry SHA changes on every re-emit.
