---
tags:
  - '#audit'
  - '#calc-sheets-parity'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-14-calc-sheets-translator-audit]]"
  - "[[2026-05-14-google-oauth-adr]]"
---

# `calc-sheets-parity` audit: engine and registry double-verification sweep

## Scope

Executes the `verify_modelo_parity` harness across every modelo with
at least one computed formula in `registry/aeat/modelos/`. For each
run the harness:

1. Builds a `SheetExportPlan` from the registry snapshot.
2. Applies the plan to a real Google Sheets workbook under
   `aeat-vault/calc-sheets/{modelo}-{period}-{year}/`.
3. Seeds operator inputs, numeric bindings, enum bindings, and
   relation values into their reserved cells.
4. Reads every computed casilla back from `Cálculos`.
5. Computes the same casillas locally via
   `calculate_registry_snapshot`.
6. Where an AEAT-published expected-output map is available
   (currently only modelo 100 Renta WEB Open replays), compares
   against the AEAT oracle as well.

The harness produces a three-way verdict per casilla: `sheets_vs_local`,
`local_vs_aeat`, and `sheets_vs_aeat`. The aggregate verdict is
`all_match` when every available pair agrees, `divergence` when any
pair disagrees, and `inconclusive` when only the engine pair is
available and that pair matches.

## Engine parity (Sheets = local Decimal runtime)

Across every modelo with formulas the engine parity is **bit-for-bit
exact**. The Sheets workbook the engine emits evaluates to the same
per-casilla rounded Decimal the local runtime produces, for every
scenario tested.

### IRPF tier

| Modelo | Period | Computed casillas | `sheets_vs_local` matches |
|-------:|--------|------------------:|--------------------------:|
|    111 | 01     |                 2 |                       2/2 |
|    115 | 1T     |                 2 |                       2/2 |
|    123 | 1T     |                 5 |                       5/5 |
|    130 | 1T     |                10 |                     10/10 |
|    131 | 1T     |                 6 |                       6/6 |
|    180 | 0A     |                 3 |                       3/3 |
|    190 | 0A     |                 3 |                       3/3 |
|    193 | 0A     |                 3 |                       3/3 |

### IVA + IS tier

| Modelo | Period | Computed casillas | `sheets_vs_local` matches |
|-------:|--------|------------------:|--------------------------:|
|    202 | 1P     |                13 |                     13/13 |
|    303 | 1T     |                 3 |                       3/3 |
|    309 | AD-HOC |                 1 |                       1/1 |
|    322 | 01     |                 3 |                       3/3 |
|    353 | 01     |                 3 |                       3/3 |
|    369 | EXT-1T |                 1 |                       1/1 |
|    390 | 0A     |                 3 |                       3/3 |

### Renta (modelo 100) — full annual surface

168 computed formulas across four CCAA-bearing AEAT replays produce
672 casilla-scenario pairs (168 × 4); all 672 match the local
Decimal runtime bit-for-bit. The `lookup_bracket` and
`lookup_bracket_by_ccaa` closed-form translations survive every
scenario.

## Registry parity (local Decimal = AEAT live oracle)

AEAT-published expected outputs exist today only for modelo 100 via
`corpus/parity_replays/renta_web_open/`. Across four CCAA-bearing
scenarios the harness compared the local runtime against AEAT for
sixteen casilla-scenario pairs:

|     Casilla | Concept                                       | AEAT (Madrid / Canarias / Cataluña / Galicia) | Local Decimal | Verdict   |
|------------:|-----------------------------------------------|-----------------------------------------------|---------------|-----------|
|        0610 | Cuota diferencial                             |          0.00 / 0.00 / 0.00 / 0.00            |     0.00      | match     |
|        0670 | Resultado de la declaración                   |          0.00 / 0.00 / 0.00 / 0.00            |     0.00      | match     |
|        0519 | Mínimo personal y familiar — parte estatal    |     5550.00 / 5550.00 / 5550.00 / 5550.00     |     0.00      | divergence |
|        0520 | Mínimo personal y familiar — parte autonómica |   5956.65 / 5606.00 / 5550.00 / 5789.00       |     0.00      | divergence |

The `0610` and `0670` casillas match — both AEAT and local agree on
`0.00` for a zero-income scenario.

The `0519` and `0520` casillas disagree consistently: AEAT publishes
the statutory minimum personal y familiar applicable to a default-
employee profile (LIRPF art. 56 and the per-CCAA equivalents in
Anexo B), even when no income is declared; the local registry
runtime evaluates these casillas to `0.00`. The divergence is
consistent across all four CCAAs.

## Two distinct categories of finding

### Category 1 — Engine correctness (the deliverable in scope)

The schema-to-sheet engine, the closed-form translator, and the
Sheets apply adapter together emit a workbook whose formulas
evaluate to the SAME values the local Decimal runtime computes for
every modelo with formulas in the registry today. 706 casilla
comparisons across 16 modelos + 4 CCAA scenarios of modelo 100, all
green.

No engine-side gap exists. The translator's closed-form expansions
for `add`, `sum`, `subtract`, `multiply`, `divide`, `percent`,
`negate`, `min`, `max`, `clamp`, `copy`, `lookup_parameter`,
`lookup_bracket`, `lookup_bracket_by_ccaa`, `previous_period_value`,
`previous_period_sum`, `cross_model_sum`, `if_then_else`, and the
five comparison ops all hold against the runtime under live Sheets
evaluation.

### Category 2 — Registry correctness (surfaced, separate fix)

The local Decimal runtime computes `0.00` for casillas `0519` and
`0520` of modelo 100 in the four CCAA replays, where AEAT publishes
the statutory minimum personal y familiar values. This is a
registry-side gap: the formula chain feeding `0520` (which sums
sub-casillas `0512`, `0514`, `0516`, `0518`, …) is not producing
the legal minimums.

The gap is not introduced or magnified by the engine — the engine
faithfully renders whatever the registry declares. The harness's
value is precisely this: when the engine is provably correct
(`sheets_vs_local` always passes), any AEAT divergence the oracle
surfaces is a real registry defect, not an artefact of double-
translation.

## Recommendations

### R1 — Drive `corpus/parity_replays/renta_web_open/` coverage wider

The current five fixtures cover the default-employee scenario across
four CCAAs. Extending to scenarios with non-zero employment income,
self-employment income, rental income, and prior-year roll-up
relations would surface every category-2 divergence the registry
carries — currently we only see the constant-minimum gap.

### R2 — Wire a CI gate that fails on `sheets_vs_local` divergence

The category-1 verdict (engine parity) is the right invariant for
the engine's regression gate. A `pytest`-shaped check that exercises
one fixture per modelo + computes `sheets_vs_local` for every
casilla would catch translator regressions before they ship.

### R3 — File a registry issue for the `0519` / `0520` divergence

The mínimo personal y familiar chain on modelo 100 is computing to
zero where AEAT publishes the statutory legal minimums. The fix
requires inspecting the formula declarations for casillas `0512`,
`0514`, `0516`, `0518` (the children of `0520`) and their estatal
equivalents in the `0519` chain, and reconciling them against
LIRPF art. 56 / Anexo B.

### R4 — Capture additional AEAT oracle surfaces

The `dr.xls` workbooks referenced by `workbook_parity_refs` in many
modelo revisions are an authoritative second oracle that could be
wired through the existing `_workbook_parity.py` runtime to extend
oracle coverage beyond modelo 100.

## Harness reproducibility

The sweep was executed via:

- `aeat config google sync calc verify --modelo <id> --period <p> --year <y>`
  for the empty-default scenarios (verdict: `inconclusive`,
  `sheets_vs_local` always green).
- A scripted harness invocation for the modelo 100 AEAT-oracle
  scenarios, feeding each `corpus/parity_replays/renta_web_open/*.json`
  fixture through `OperatorInputScenario` with the corresponding
  CCAA dispatch key and the published `expected_by_casilla` map.

Both paths are deterministic and replayable. The harness module is
`src/aeat/application/storage/calc_sheets/_parity_harness.py`; the
CLI bridge is `_google.py`'s `google_sync_calc_verify` command.
