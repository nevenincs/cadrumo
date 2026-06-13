---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S202'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# `declaracion-extraction-architecture` W10.P45.S202 — M130 corpus regeneration with formula-consistent values

## Step

Regenerate 15 M130 corpus fixtures (`src/aeat/tests/fixtures/justificantes/130/`)
with formula-consistent casilla values so the verification chain
(`test_verification_chain_m130_engine_recomputes_closure_casilla_19`) transitions
all 15 specimens from FORMULA-MISMATCH to VERIFIED.

## Execution

### UNIT 1 — Root-cause audit

The 15 existing M130 corpus PDFs (2021-2T through 2024-4T) were real AEAT-generated
PDFs (sanitised). All casilla values had been uniformly set to `1.000,00` as the
sanitisation placeholder. The bbox_anchored extractor extracted these values correctly,
but when the verification chain fed them to the calculation engine:

- The engine computed `casilla 19` via the formula chain (formulas/0001-formulas.toml,
  formulas/0002-formulas.toml, parameters/0001-parameters.toml).
- The real PDFs printed `19 = 1.000,00` but the engine recomputed different values
  because the leaf inputs (01, 02, 03, 05, 06, etc.) were all `1.000,00` — a numerically
  inconsistent assignment where e.g. `04 = max(0, 03 * 20%) = 200` but the printed PDF
  showed `04 = 1.000,00`.
- Result: 15 FORMULA-MISMATCH failures.

### UNIT 2 — M130 formula DAG

Registry source: `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/`

Formula chain (all other leaf inputs = 0, `irpf.previous_year_economic_activity_net_income` binding = 0):

| Casilla | Kind     | Formula                                                              |
|---------|----------|----------------------------------------------------------------------|
| 01      | bound    | ingresos cumulative — set to 0 (absent from fixture)                 |
| 02      | manual   | gastos — set to 0 (absent)                                           |
| 03      | bound    | rendimiento neto cumulative — leaf input printed in PDF               |
| 04      | computed | `max(0, 03 × 20%)` (`irpf.direct_estimation_fractional_payment_rate`)|
| 05      | manual   | pagos fraccionados anteriores — 0 (absent)                           |
| 06      | manual   | retenciones — 0 (absent)                                             |
| 07      | computed | `04 − 05 − 06`                                                       |
| 08      | manual   | volumen ingresos agrario — 0 (absent)                                |
| 09      | computed | `08 × 2%` (`irpf.agriculture_fractional_payment_rate`)               |
| 10      | manual   | retenciones agrario — 0 (absent)                                     |
| 11      | computed | `09 − 10`                                                            |
| 12      | computed | `max(0, 07 + 11)`                                                    |
| 13      | computed | 100 EUR (step: `prev_year_income=0 ≤ 9000 → 100`)                   |
| 14      | computed | `12 − 13`                                                            |
| 15      | bound    | resultados negativos anteriores — 0 (binding supplied as 0)          |
| 16      | manual   | deduccion vivienda — 0 (absent)                                      |
| 17      | computed | `(14 − 15) − 16` (c01=0 → condition `c01>0` is False)               |
| 18      | manual   | resultado autoliquidaciones anteriores — 0 (absent)                  |
| 19      | computed | `17 − 18` — closure casilla                                          |

Simplified: `c19 = max(0, c03 × 20%) − 100`.

### UNIT 3 — Implementation

Added to `src/aeat/tests/fixtures/justificantes/_generate.py`:

- `_fmt_spanish(d: Decimal)` — formats Decimal to Spanish monetary string (`5.000,00`).
- `_Modelo130CorpusFixture` — frozen dataclass with fields `filename, ejercicio, periodo, tax_id, c03, c19`.
- `_compute_m130_closure(c03: Decimal) -> Decimal` — replicates the M130 formula chain
  arithmetic (no engine import; arithmetic mirrors formulas/0001-formulas.toml +
  formulas/0002-formulas.toml + parameters/0001-parameters.toml). Returns `c19`.
- `_MODELO_130_CORPUS_FIXTURES` — 15 fixtures with distinct `c03` values (5000–14000 EUR,
  varying per specimen). `c19` set via `_compute_m130_closure(c03)` at module load time.
- `_draw_modelo_130_corpus(c, fixture)` — renders a single-page synthetic PDF:
  - `NIF Presentador: Y0000001S` (required by `_extract_tax_id`).
  - Box number `03` at x=464.0 (within anchor_x_min=450, anchor_x_max=480).
  - Box number `19` at x=464.0 on a separate row.
  - Spanish-formatted value at x=535.0 same y-row as each box number.
  - Rendered with `invariant=True` for byte-deterministic output.
- Generation loop added to `main()`.

### UNIT 4 — Leaf-input scheme per specimen

| Specimen  | c03 (rendimiento neto) | c19 (resultado final) |
|-----------|------------------------|-----------------------|
| 2021-2T   | 5000.00                | 900.00                |
| 2021-3T   | 7500.00                | 1400.00               |
| 2021-4T   | 10000.00               | 1900.00               |
| 2022-1T   | 5200.00                | 940.00                |
| 2022-2T   | 7800.00                | 1460.00               |
| 2022-3T   | 9100.00                | 1720.00               |
| 2022-4T   | 11000.00               | 2100.00               |
| 2023-1T   | 5400.00                | 980.00                |
| 2023-2T   | 8100.00                | 1520.00               |
| 2023-3T   | 10500.00               | 2000.00               |
| 2023-4T   | 13000.00               | 2500.00               |
| 2024-1T   | 5600.00                | 1020.00               |
| 2024-2T   | 8400.00                | 1580.00               |
| 2024-3T   | 11200.00               | 2140.00               |
| 2024-4T   | 14000.00               | 2700.00               |

Formula derivation approach: `_compute_m130_closure` hand-replicates the registry
formula arithmetic (not engine-driven at generation time) with a comment citing each
TOML formula source. The engine independently evaluates the same formulas at test time —
no circular dependency.

### UNIT 5 — Verification chain result

```
uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/test_verification_chain.py::test_verification_chain_m130_engine_recomputes_closure_casilla_19 -v --tb=short
```

**Before:** 15 FORMULA-MISMATCH (all failed)
**After:** 15 VERIFIED (all 15 passed in 55.93s)

### UNIT 6 — Determinism check

Two consecutive generator runs produce byte-identical PDFs (SHA-256 prefix unchanged).
`invariant=True` + deterministic `_compute_m130_closure` arithmetic ensure stable output.

### UNIT 7 — Regression check

```
uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/ src/aeat/adapters/outbound/aeat/sede/ -q --tb=line
```

Exit code 0. No regressions introduced.

## Honest verdict

All 15 M130 specimens transitioned from FORMULA-MISMATCH to VERIFIED. No residual
FORMULA-MISMATCH cases. No formula gaps surfaced — the registry formula chain is
complete and the synthetic fixtures exercise it correctly.

The `_compute_m130_closure` helper is a maintenance obligation: if the registry
formula parameters change (e.g. the 20% rate or the casilla-13 step function
thresholds), the helper must be updated and the fixtures regenerated. The non-tautology
property is preserved because the generator's arithmetic and the engine's runtime
TOML evaluation are independent code paths.
