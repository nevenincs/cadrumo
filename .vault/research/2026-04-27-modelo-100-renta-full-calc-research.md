---
tags:
  - '#research'
  - '#modelo-100-renta-full-calc'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-21-modelo-100-renta-research]]"
  - "[[2026-04-21-modelo-100-renta-adr]]"
  - "[[2026-04-21-modelo-100-renta-plan]]"
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-27-modelo-303-calc-verify-research]]"
  - "[[2026-04-27-modelo-115-calc-verify-research]]"
  - "[[2026-04-27-modelo-131-calc-verify-research]]"
  - "[[2026-04-27-modelo-111-calc-verify-research]]"
  - "[[2026-04-27-modelo-123-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
  - "[[2026-04-27-modelo-123-calc-verify-adr]]"
---



# `modelo-100-renta-full-calc` research: full-form RENTA universe across 2024/2025/2026

This research grounds the `#317` megaproject mandate to deliver
calc-verify-roundtrip coverage for the **complete** Modelo 100 (RENTA /
IRPF anual) universe across tax years 2024, 2025, and 2026. The mandate
explicitly closes `#317` (Tier-L per-modelo entry), `#341` (RENTA
hardening umbrella), `#342` (M100 2024 full-form), `#343` (M100 2025
full-form), and `#344` (M100 2026 full-form) in a single PR.

The 2026-04-21 prior triplet (`modelo-100-renta`) scoped a 27-casilla
**summary-block MVP** that landed as `modelo_100.summary.2025`. That
prior ADR explicitly defers full-anexo coverage to a follow-up
sub-EPIC. This research is the foundation of that follow-up; the user's
2026-04-27 directive expands scope without bound to drive the codebase
to comprehensive Spanish IRPF regulation coverage.

## 1. The M100 RENTA universe — scope inventory

Modelo 100 is structurally the largest Spanish tax form. Its
regulation surface spans nine anexos (A through Ñ), three régimenes de
estimación for actividades económicas, seventeen autonomous communities
plus Ceuta and Melilla, and three tax years that each carry their own
escalas, mínimos, and deducciones. The figure below sketches the axes
the implementation must handle.

```
M100 universe
├── Anexo A — Identificación + datos personales + régimen económico
│            matrimonial + descendientes + ascendientes + discapacidad
├── Anexo B1 — Rendimientos del trabajo
│            • Salarios, pensiones, retenciones (LIRPF arts. 17-20)
│            • Reducción art. 18 (rendimientos irregulares)
│            • Gasto deducible cotización SS, otros (art. 19)
│            • Reducción art. 20 (rendimientos del trabajo) — variable
│              por base imponible
├── Anexo B2 — Rendimientos del capital mobiliario
│            • Dividendos, intereses, ganancias > 2 años (LIRPF arts. 25-26)
│            • Retenciones M123 al 19% (LIRPF art. 101.4 + RIRPF art. 90)
├── Anexo C  — Rendimientos del capital inmobiliario
│            • Alquileres con/sin reducción 60% vivienda habitual
│              (LIRPF art. 23.2)
│            • Gastos deducibles, amortización 3% construcción
│            • Imputación de rentas inmobiliarias (LIRPF art. 85)
├── Anexo D  — Actividades económicas (the big one — autónomo case)
│            ├─ Estimación directa normal (P&L per LIS)
│            ├─ Estimación directa simplificada (5% gastos genéricos cap,
│            │   RIRPF art. 30)
│            ├─ Estimación objetiva (módulos, RIRPF art. 32)
│            ├─ Inventario (LIS art. 17 — FIFO / PMP / coste medio)
│            └─ Amortizaciones (LIS arts. 12-14, libertad amort. PYMES
│                art. 102)
├── Anexo E  — Ganancias y pérdidas patrimoniales
│            • Compensación con rendimientos (LIRPF arts. 33-39)
│            • Regla FIFO acciones (art. 37)
├── Anexo F  — Bases imponibles + reducciones + mínimos
│            • Base imponible general / base del ahorro
│            • Reducciones de la base imponible (planes pensiones art. 51,
│              tributación conjunta art. 84)
│            • Mínimo personal y familiar (LIRPF arts. 56-61)
├── Anexo G  — Cuotas (íntegra estatal + autonómica, líquidas, deducciones
│              de la cuota)
│            • Tarifa estatal LIRPF art. 63
│            • Tarifa autonómica general LIRPF art. 74 + Ley CCAA
│            • Tipos del ahorro LIRPF art. 66 (multi-bracket 19/21/23/27/30%)
│            • Deducciones estatales (vivienda transitoria, donativos,
│              maternidad, familia numerosa, alquiler transitorio)
└── Anexo Ñ  — Deducciones autonómicas (17 CCAA + Ceuta/Melilla 50%)

Per año:
├── 2024 — anchored by Orden HAC/265/2025 (Modelo 100 2024 template)
├── 2025 — anchored by per-año Orden HAC + per-CCAA Ley de Presupuestos
└── 2026 — anchored by primary BOE sources only (training data unreliable)
```

País Vasco and Navarra are **explicitly out of scope** (foral / convenio
económico — separately handled per `#424`).

Conservative estimate: ~600-1000 computed casillas if every BOE-printed
cell is encoded as a `FormulaDefinition`. The implementation will tier
this — see §8 architectural options.

## 2. Existing M100 surface audit

The repository already carries a non-trivial M100 footprint that this
work expands rather than replaces. The audit below enumerates each
artefact and the gap from the megaproject DoD.

| Existing artefact | Path | Coverage | Gap to megaproject DoD |
|---|---|---|---|
| Summary ruleset (2025 only) | `src/aeat/domain/formulas/_rulesets/modelo_100_summary_2025.py` | 12 casillas (4 inputs + 4 inputs + 4 computed). `variant="summary"`; default slot reserved | Need full-form 2024/2025/2026 default-variant rulesets |
| Summary ruleset tests | `src/aeat/domain/formulas/_rulesets/test_modelo_100_summary_2025.py` | Engine-anchored; 6 cases | Need per-anexo per-year worked examples |
| Borrador summary extractor | `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py` | 27 casilla regex map | Need multi-anexo extension for 2024/2025/2026 |
| Synthetic generator | `tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_100_generator.py` | `Modelo100GenParams` Pydantic v2; `casilla_values: Mapping[str, Decimal]` flexible | Multi-anexo layout; per-año variant |
| Declaración parser dir | `src/aeat/adapters/inbound/declaracion/_parsers/modelo_100/{_extractor.py,_scanner.py}` | Three template revisions: 2021 legacy, 2022 modern, 2023 modern. 84/83/86 casillas. `ExtractionStatus.UNVERIFIABLE` (empty required-set) | Need 2024/2025/2026 template revisions; tighter required-set |
| Modelo entry metadata | `src/aeat/domain/modelos/_entries/modelo_100.py` | LIRPF art. 27 citation + Orden HAC/265/2025 (BOE-A-2025-5049) | Already aware of M100 2024 Orden — useful BOE anchor |
| Borrador-dispatch CLI | `aeat filing import --from-borrador` | Routes M100 PDFs through `aeat.adapters.inbound.borrador` parser | M100 is the **only** Tier-L modelo that dispatches via `--from-borrador`; this is unique |
| Kent integration test | `tests/integration/test_kent_workflows.py::TestKentImportsModelo100SummaryBorrador` | 3 cases (EN happy / ES happy / drift NEEDS_REVIEW) | Extend with per-año 2024/2025/2026 + multi-anexo cases |
| Coverage matrix row | `docs/coverage/modelos.md` row for M100 | Schema 🚧, ruleset 🚧 (summary 12), CLI ✅ (`--from-borrador`), declaración ✅ (summary MVP) | Flip to ✅ in every applicable column |

**The unique M100 dispatch path.** Among Tier-L modelos M111, M115,
M123, M130, M131, M303 — every one dispatches via
`aeat filing import --from-declaracion`. M100 alone dispatches via
`aeat filing import --from-borrador`. This is a load-bearing fact: any
Kent integration test class for the full-form M100 must continue to use
`--from-borrador`, not `--from-declaracion`. The verdict line emits as
`Verification status: VERIFIED (ruleset=modelo_100.summary.2025)` for
the existing summary path. The full-form ruleset will mirror this with
`ruleset=modelo_100.<año>` (default variant per the registry's variant
slot reservation).

**The variant slot.** The summary ruleset comment in
`modelo_100_summary_2025.py` explicitly reserves the **default variant
slot** for the full-form M100 ruleset:
`"explicit variant='summary' reserves the default slot for the
(eventual) full-form modelo_100 ruleset without a registry-overlap
conflict"`. The full-form 2024/2025/2026 rulesets I author will use the
default variant — `ruleset_id` patterns `modelo_100.2024`,
`modelo_100.2025`, `modelo_100.2026` — and coexist with the existing
`modelo_100.summary.2025` slot.

## 3. Reference patterns from 5 sibling Tier-L impls

The five landed Tier-L per-modelo calc-verify-roundtrip implementations
(M111, M115, M123, M130, M131, M303 — six modelos all dated 2026-04-27)
establish a uniform pattern. The full pattern map captured below is the
controlling reference for M100 authoring.

### Module-level shape per `modelo_<NNN>_<YYYY>.py`

Every per-year ruleset module follows the same skeleton: module
docstring with year-delta narrative; `_EFFECTIVE_FROM` / `_EFFECTIVE_TO`
date constants; module-level `_label(es, en, hu)` helper returning
`Translatable`; module-level `_CITATIONS` tuple constructed via
`make_citation`; module-level `_CASILLAS` tuple constructed via
`casilla()`; module-level `_FORMULAS` tuple constructed via the
`formula()` helper which auto-wraps body in terminal
`RoundFormula(digits=2, ROUND_HALF_UP)`; module-level `_PARAMETERS`
`ParameterTable`; and the public `RULESET: Ruleset` constant.

### Casilla discipline

Every `CasillaDefinition` carries: `casilla_id` (regex-validated 2-5
digit string); `label` `Translatable` mapping ES/EN/HU; `computed` bool
flag; `data_type` (defaults to `CasillaDataType.CURRENCY_EUR`);
`legal_basis` tuple (post-`#339` mandatory if `computed=True`).
Citations are usually a shared module-level tuple referenced by every
computed casilla, NOT one citation per casilla.

### Formula DSL helpers (from `_common.py`)

| Helper | Produces | Notes |
|---|---|---|
| `casilla(...)` | `CasillaDefinition` (currency_eur) | trilingual label required |
| `formula(casilla_id, formula_id, body)` | `FormulaDefinition` | wraps body in terminal `RoundFormula(2dp, HALF_UP)` |
| `ref("NNN")` | `CasillaRef` | by casilla id |
| `lit("X.YY")` / `lit(int)` | `Literal(Decimal)` | rejects float |
| `param("name")` | `ParamRef` | resolves via `ParameterTable` |
| `add_op(*operands)` | `AddFormula` | n-ary |
| `sub_op(lhs, rhs)` | `SubFormula` | binary |
| `mul_op(*operands)` | `MulFormula` | n-ary |
| `div_op(lhs, rhs, quantize="0.0001")` | `DivFormula` | precision cap |
| `min_op` / `max_op` | `Min/MaxFormula` | n-ary |
| `clamp_pos(x)` | `ClampPositiveFormula` | `max(0, x)` |
| `percent(rate, base)` | `PercentFormula` | rate is decimal fraction |
| `percent_from_whole(rate_ref, base)` | `PercentFormula` with `/100` | when rate is whole-percent extracted from PDF |
| `brackets(operand, steps=(...))` | `BracketsFormula` | step function; final bracket has `upper_inclusive=None` |
| `round2(x)` | `RoundFormula(2dp)` | rare; usually implicit via `formula()` |
| `make_citation(source, article, quoted_text_es, *, url)` | `LegalCitation` | retrieval_date defaults to 2026-04-17; override per BOE consult date |

### What the DSL does NOT directly provide

- Conditional (if-then-else): not in DSL. Workaround: lift conditional
  into multiple casillas + `min_op`/`max_op`/`clamp_pos`.
- Absolute value: not in DSL. Workaround: derive by casilla design.
- Rounding modes other than `ROUND_HALF_UP`: not exposed. Every formula
  rounds half-up at terminal.

### Citation pattern

`make_citation` shape: `source` (`LegalCitationSource` enum: LEY,
REAL_DECRETO, REGLAMENTO, ORDEN_MINISTERIAL, MANUAL_PRACTICO, BOE);
`article` (string, e.g. `"100.1"`, `"110.3.c"`); `quoted_text_es`
(curated Spanish summary, validated non-empty); `url` (HttpUrl, BOE
permanent format `https://www.boe.es/buscar/act.php?id=BOE-A-XXXX-NNNNN`
optionally `&p=YYYYMMDD&tn=1` for date-pinned consult).

The `KnownBadCitation` blocklist (post-wave-69) catches the 14 most
common citation errors — e.g. citing LIRPF art. 67 for "cuota íntegra
estatal" when art. 67 is "cuota líquida estatal"; correct anchor is
art. 62. This is enforced at `LegalCitation` model construction.

### Test pattern

Module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`
(per the brief; landed M123 follows this pattern, replacing earlier
`domain_local_state` choice). Per-modelo test files carry: `_provided()`
helper returning a clean Decimal fixture; one `test_consistent_*_is_clean`
case; one `test_external_worked_example_*` case anchoring expected
values to a specific BOE article (NOT to the ruleset itself); threshold-
edge cases at ε below and ε above each bracket boundary; zero-boundary
case (all inputs = 0); per-year regression case (`test_2025_no_drift_from_2024`).

### Mutation harness contract

The harness auto-discovers rulesets via `ALL_RULESETS` import. **The
per-modelo node count must be added to the `EXPECTED_COUNTS` dict in
`test_mutator_kill_rate.py`**: keys are `sub_op`,
`percent_rate_literal`, `percent_rate_param`,
`percent_rate_compound_skipped`, `percent_rate_casilla_ref_skipped`,
`brackets_threshold_non_terminal`, `mul_div_scalar`. The
`test_mutator_exhaustiveness.py` orphan-node defense auto-fails if any
new Formula/Operand subclass appears in `aeat.domain.formulas` without
mutator registration, but per-ruleset counts are explicit (forces
coverage review).

### Per-year delta strategy — **full re-author per year, NOT inheritance**

Each year ships its own file (`modelo_NNN_2024.py`, `_2025.py`,
`_2026.py`). Formula IDs are year-scoped (`modelo_NNN.2025.<reason>`).
When the year's rules are unchanged from prior, the file is a structural
clone with new effective dates and new formula IDs — verbose but
maintains audit traceability.

### Per-CCAA precedent — none

No landed modelo carries per-CCAA logic. The closest precedent is the
M130 La Palma 60% reduction overlay, which is **caller-gated**
(applied post-formula at audit time via overlay). For M100, per-CCAA
deductions are too central to defer to overlays — they live on Anexo Ñ
casillas and feed the cuota líquida total.

### Cross-anexo structure precedent — none

No landed modelo is structured by anexo. All are flat single-file
rulesets (M130 = 19 casillas; M303 = 33 casillas). M100 will exceed
single-file limits — see §8 architectural decision.

## 4. Foundations layer — Pydantic + DSL + audit + registry

### Pydantic v2 strict frozen extra=forbid is universal

Every record-shaped object in the formula layer is Pydantic v2:
`CasillaDefinition`, `LegalCitation`, `Ruleset`, `ParameterTable`,
`ParameterValue`, `FormulaDefinition`, every Formula AST node type
(`AddFormula`, `SubFormula`, `MulFormula`, `DivFormula`, `MinFormula`,
`MaxFormula`, `ClampPositiveFormula`, `PercentFormula`, `BracketsFormula`,
`RoundFormula`), every Operand leaf (`Literal`, `CasillaRef`, `ParamRef`),
and every `Bracket`. All have `strict=True`, `frozen=True`,
`extra="forbid"`. **No `dict[str, Any]` smell anywhere in the layer.**
Extending the Anexo D inventory + amortization model space MUST keep
this discipline — every Pydantic v2, no bare dicts.

### Ruleset validation

`Ruleset._validate()` enforces: `effective_to >= effective_from`; no
duplicate casilla IDs; every formula's `casilla_id` is declared and
`computed=True`; no duplicate `formula_id`s; every formula's
casilla/param references exist; every computed casilla has a formula;
DAG acyclicity via `TopologicalSorter` (raises `FormulaCycleError`
on cycle).

### Citation validator (post-`#339`)

`CasillaDefinition._require_legal_basis_for_computed()` raises
`RulesetValidationError` if `computed=True` and `legal_basis` is empty
or absent. Plus `LegalCitation._reject_known_bad_citations()` which
hits the `KnownBadCitation` blocklist at construction time.
`aeat audit rulesets citations` CLI walks every registered ruleset and
emits per-ruleset coverage + aggregate report; exit 1 on any gap.

### Mutation harness layers

- Operand-swap (`test_operand_swap_mutation.py`): exercises every
  `SubFormula` node by swapping its operand pair.
- Percent-rate (`test_percent_rate_mutation.py`): exercises rate of
  every `PercentFormula`.
- Brackets-threshold: exercises non-terminal bracket boundaries.
- Mul/Div scalar: exercises Literal operands in `MulFormula`/`DivFormula`.
- Zero-boundary (`test_zero_boundary_coverage.py`): asserts all-zero
  inputs produce all-zero computeds.
- Kill-rate aggregator (`test_mutator_kill_rate.py`): asserts per-modelo
  per-mutator kill counts via `EXPECTED_COUNTS` dict.
- Exhaustiveness (`test_mutator_exhaustiveness.py`): orphan-node defense.

### Errors + logging

All domain errors inherit from `aeat.core.errors.AeatError`. Formula layer
exposes `FormulasError`, `RulesetValidationError`, `FormulaCycleError`,
`CasillaNotDefinedError`, `MissingRulesetError`, `AmbiguousPeriodError`,
`EvaluationError`, `AuditDiscrepancyError`. Logging uses
`aeat.core.logging.get_logger(__name__)` (never bare logging); the logger
applies `SecretScrubbingFilter` automatically (NIF, api_key, etc.).

### Synthetic factory layer

`aeat.domain.testing` exposes `FilingRecord`, `FixtureCasilla`,
`FilingRecordPeriodKind`, `FilingRecordScenario`, plus
`load_filing_history`, `compute_record_id`, `synthesize_filing_draft`.
Every fixture file carries top-level `synthetic: true` literal +
`_comment` warning string — strict pydantic validation enforces.

### Registry pattern

`src/aeat/domain/formulas/_rulesets/__init__.py`: import each `RULESET` with
alias `MODELO_<code>_<year>`, add to `ALL_RULESETS` tuple in numeric +
year ascending order, mirror in `__all__`. New M100 rulesets land at
`MODELO_100_2024`, `MODELO_100_2025`, `MODELO_100_2026` (default
variant) alongside the existing `MODELO_100_SUMMARY_2025`.

## 5. Per-anexo casilla inventory (preliminary)

The casilla IDs below are drawn from the existing borrador extractor
(`_SUMMARY_CASILLAS`), the declaración parser layouts for tax years
2021/2022/2023, and the Modelo 100 BOE Orden HAC instruction manuals.
Every printed `computed=True` casilla on the BOE template will be
encoded as a `FormulaDefinition`; the inventory is exhaustive at
implementation time but is sketched here as the architectural map.

### Anexo A — datos personales

Identification only — no computed casillas. Anexo A drives applicability
of subsequent anexos (régimen económico matrimonial, dependent count,
discapacidad).

### Anexo B1 — rendimientos del trabajo (LIRPF arts. 17-20)

| Casilla | Role | LIRPF anchor | Notes |
|---|---|---|---|
| 0001-0007 | Ingresos íntegros (sueldos, pensiones, prestaciones) | art. 17 | Inputs from M190 retentions data |
| 0008-0009 | Gasto deducible — cotización SS, cuotas colegiales | art. 19 | Capped per art. 19.2 |
| 0010 | Gasto otros (movilidad geográfica) | art. 19 | Conditional |
| 0011-0012 | Reducción art. 18 (rendimientos irregulares) | art. 18 | 30% reducción capped |
| 0021 | Rendimiento neto previo (input - gastos) | art. 20 | Computed |
| 0022 | Rendimiento neto reducido | art. 20 | Computed; reducción tabla 1 (variable) |

### Anexo B2 — rendimientos del capital mobiliario (LIRPF arts. 25-26)

| Casilla | Role | LIRPF anchor | Notes |
|---|---|---|---|
| 0028-0035 | Dividendos, intereses cuentas, intereses títulos públicos | art. 25 | Inputs from M123 retentions |
| 0036-0040 | Gastos administración + custodia (deducibles) | art. 26 | Capped |
| 0049 | Rendimiento neto reducido capital mobiliario | art. 26.2 | Computed |

### Anexo C — rendimientos del capital inmobiliario (LIRPF arts. 22-24, 85)

| Casilla | Role | LIRPF anchor | Notes |
|---|---|---|---|
| 0061-0065 | Ingresos arrendamiento por finca | art. 22 | Per finca |
| 0066-0070 | Gastos deducibles por finca | art. 23.1 | Reparación, financiación, IBI |
| 0072 | Amortización 3% construcción | art. 23.1 | 3% sobre mayor de coste/valor catastral |
| 0078 | Reducción 60% vivienda habitual | art. 23.2 | Solo cuando arrendatario uso vivienda |
| 0085-0089 | Imputación rentas inmobiliarias | art. 85 | 1.1% / 2% valor catastral |
| 0107 | Rendimiento neto reducido capital inmobiliario | art. 23.3 | Computed |

### Anexo D — actividades económicas (the big anexo)

Sub-divides into three régimenes:

#### D — estimación directa normal (LIRPF art. 28)

P&L following LIS principles. Inventory per LIS art. 17 (FIFO / PMP /
coste medio). Amortizaciones per LIS arts. 12-14 (lineal default,
libertad amort. PYMES per art. 102). Provisiones per LIS arts. 13-14.

| Casilla group | Role | Anchor |
|---|---|---|
| 0140-0149 | Ingresos de explotación + variación existencias | LIS art. 17 |
| 0150-0159 | Compras + variación existencias compras | LIS art. 17 |
| 0160-0165 | Gastos de personal | LIS art. 12 |
| 0166-0175 | Servicios exteriores, tributos, otros | LIS art. 13 |
| 0176-0180 | Amortización inmovilizado material | LIS art. 12.1 lineal |
| 0181-0184 | Amortización inmovilizado intangible | LIS art. 12.2 |
| 0185-0189 | Amortización acelerada PYMES (libertad) | LIS art. 102 |
| 0190-0199 | Provisiones, deterioros | LIS arts. 13-14 |
| 0175 | Rendimiento neto E.D. normal (the result) | LIRPF art. 28 |

#### D — estimación directa simplificada (RIRPF art. 30)

Identical to E.D. normal **except**: gastos de difícil justificación
capped at 5% of rendimiento neto positivo, with annual cap (currently
2 000 EUR; verify per año). The 5% cap is a hard rule; encoded as a
`min_op(percent(0.05, rendimiento_neto_pos), lit("2000.00"))`.

#### D — estimación objetiva / módulos (RIRPF art. 32)

Coefficient lookups per actividad (tabla en Orden HAC anual). Out of
direct scope unless a real Orden HAC table is encoded. Pattern mirrors
M131 módulos coverage: caller supplies módulos values; ruleset verifies
the aggregation chain.

### Anexo E — ganancias y pérdidas patrimoniales (LIRPF arts. 33-39)

| Casilla group | Role | Anchor |
|---|---|---|
| 0306-0309 | Transmisión elementos patrimoniales (acciones, inmuebles) | art. 33 |
| 0317-0320 | Cálculo ganancia/pérdida (FIFO acciones) | art. 37 |
| 0395-0400 | Saldo neto ganancias/pérdidas a integrar en base general / ahorro | arts. 33.5, 49 |

### Anexo F — bases imponibles + reducciones + mínimo personal (LIRPF arts. 47-61)

| Casilla group | Role | Anchor |
|---|---|---|
| 0420-0432 | Suma bases imponibles general | art. 48 |
| 0433-0444 | Suma base imponible ahorro | art. 49 |
| 0435 | Base imponible general (input/computed) | art. 48 |
| 0445-0455 | Reducciones base imponible general (planes pensiones art. 51, tributación conjunta art. 84) | arts. 51-54, 84 |
| 0460 | Base imponible ahorro | art. 49 |
| 0500 | Mínimo personal y familiar (suma) | art. 56 |
| 0505 | Mínimo del contribuyente | art. 57 |
| 0510 | Mínimo descendientes (1º/2º/3º/4º+ + <3 años bonus) | art. 58 |
| 0515 | Mínimo ascendientes (>65 / >75) | art. 59 |
| 0520 | Mínimo discapacidad (33-65% / >65% / asistencia) | art. 60 |
| 0545 | Base liquidable general | art. 50 |
| 0555 | Base liquidable ahorro | art. 50 |

### Anexo G — cuotas + deducciones de la cuota (LIRPF arts. 62-80)

| Casilla group | Role | Anchor |
|---|---|---|
| 0550 | Cuota íntegra general estatal — apply tarifa estatal a base liquidable general | art. 63 escala estatal |
| 0551 | Cuota íntegra general autonómica — apply tarifa autonómica a base liquidable general | art. 74 + Ley CCAA |
| 0560 | Cuota íntegra del ahorro estatal — multi-bracket | art. 66 (19/21/23/27/30%) |
| 0561 | Cuota íntegra del ahorro autonómica | art. 76 |
| 0595 | Cuota íntegra total | sum(0550, 0551, 0560, 0561) |
| 0610-0619 | Deducciones estatales — vivienda habitual transitoria, donativos (Ley 49/2002), maternidad art. 81, familia numerosa art. 81 bis | arts. 68-69 |
| 0620 | Total deducciones estatales | sum |
| 0622 | Total deducciones autonómicas (Anexo Ñ) | sum |
| 0630 | Total deducciones | sum |
| 0698 | Cuota líquida total = max(0, 0595 - 0630) | arts. 67, 77 |
| 0699 | Retenciones e ingresos a cuenta | art. 99 |
| 0700 | Pagos fraccionados M130/M131 | art. 99 |
| 0720 | Cuota resultante / cuota diferencial | art. 79 |
| 0721 | Resultado a ingresar / a devolver | art. 79 + ingresos/devoluciones complementarias |

### Anexo Ñ — deducciones autonómicas (17 CCAA + Ceuta/Melilla)

Per LIRPF art. 46.bis each CCAA sets its own deductions. The full
catalogue is the largest single research surface — see §6.

## 6. Per-CCAA catalogue (BOE + AEAT manual práctico anchored)

The CCAA research stream returned the following catalogue covering 15
ordinary CCAAs (excluding País Vasco / Navarra foral regimes) plus
Ceuta/Melilla. The full per-deduction table is preserved in the
rule-delta reference manifest; this section captures the architectural
inventory the ADR must address.

### 6.1 Important correction — Ceuta/Melilla is 60% (not 50%)

The brief stated Ceuta + Melilla as "50% reducción". **Primary-source
verification corrects this to 60%**: LIRPF art. 68.4 was modified by
Ley 6/2018 (PGE 2018) which raised the reducción from 50% to 60% with
effects from 2018+. The 60% rate has been stable through 2024, 2025,
2026 with no announced change.

**Naturaleza:** Ceuta/Melilla deduction is a **STATE deduction** applied
on the **total cuota íntegra** (estatal + autonómica conjuntamente),
NOT a CCAA deduction per LIRPF art. 46 bis. Ceuta and Melilla are
ciudades autónomas — not Comunidades Autónomas — and lack potestad
LIRPF art. 46 bis. They publish their own benefits on tributos cedidos
(ITP, ISD) but not on IRPF.

**Reglas vigentes 2024-2026:**

- Residentes habituales en Ceuta/Melilla (≥3 años): 60% sobre la cuota
  íntegra total proporcional a las rentas obtenidas en Ceuta/Melilla.
  Tras 3 años de residencia efectiva, también pueden deducir 60% sobre
  rentas obtenidas FUERA del territorio si al menos 1/3 del patrimonio
  neto está allí ubicado.
- Residentes <3 años: 60% sobre rentas obtenidas en Ceuta/Melilla
  únicamente.
- No residentes: 60% sobre la cuota correspondiente a rentas obtenidas
  en Ceuta/Melilla, con exclusiones específicas (rendimientos del
  trabajo, ganancias patrimoniales sobre bienes muebles, IIC, depósitos
  no participan).
- Tope: la deducción no puede exceder del 60% de la cuota íntegra total.

**Fuente:** AEAT manual práctico 2024 cap. 16; manual ayuda 2025 §9.5.1.

### 6.2 Per-CCAA deduction inventory (counts + scope)

Total per CCAA (deduction count for ejercicio 2025; 2026 mostly =):

| CCAA | 2024 dedns | 2025 dedns | 2026 status | Tarifa autonómica | Notable 2025 NEW |
|---|---|---|---|---|---|
| Andalucía | 14 | 16 | **published Ley 8/2025** — Δ alquiler/nacimiento universal | 5 brackets, top 22,5% (60k+) | ejercicio físico, gastos veterinarios, celiaquía |
| Aragón | 21 | 19 | unverifiable | 5+ brackets, top 25,0% | acogimiento Ucrania suprimida |
| Asturias | 26 | 27 | unverifiable | top 25,5% | celiaquía NEW |
| Illes Balears | 26 | 26 | unverifiable | top 25,0% | viv. ocupada ilegalmente NEW; hipoteca variable suprimida |
| Canarias | 29 | 29 | unverifiable | top 26,0% | inalterado |
| Cantabria | 18 | 21 | unverifiable | top 24,5% | residencia despoblada, impatriados, arrend. vacía NEW |
| Castilla-La Mancha | 25 | 27 | unverifiable | top 22,5% | ahorro inversión vivienda, perros asistencia |
| Castilla y León | 18 | 18 | unverifiable | 5 brackets, top 21,5% | inalterado |
| Cataluña | 11 | 13 | unverifiable | 9 brackets, top 25,5% | alquiler víctimas violencia, coop. agraria viv. |
| Comunitat Valenciana | 40 | 41 | partial (Ley 5/2025 + 6/2025) | 11 brackets, top 29,5% (200k+) | nacim. discapacidad separado, formación musical |
| Extremadura | 15 | 19 | unverifiable | top 22,5% | impatriados, ELA ayudas, ELA general |
| Galicia | 21 | 25 | unverifiable | top 22,5% | arrend. vac., libros Galicia, talidomida, ELA |
| Madrid | 23 | 23 | unverifiable | 5 brackets, top 20,5% (deflactado 2024) | inalterado (Δ deflactación 2024 ya aplicada) |
| Murcia | 21 | 28 | unverifiable | top 22,5% | veh. eléctricos, recarga, gafas, deporte, raras, eco. social, vet. |
| La Rioja | 21 | 24 | unverifiable | top 27,0% | org. prof. agrarias, celiaquía, hipoteca variable Δ |

**Total deduction count (ejercicio 2025):** ~336 deduction rules across
15 CCAAs. Times 3 años = ~1008 rule-rows for full coverage. This is
**~5-10× any single sibling Tier-L modelo** — confirms the megaproject
scoping.

### 6.3 Per-CCAA tarifa autonómica general (5 highest-population)

The five highest-population CCAAs override the LIRPF default tarifa
autonómica. Full bracket tables for 2024/2025/2026 below — values
verified against AEAT manual práctico and per-CCAA Decreto Legislativo.

#### Madrid (Decreto Legislativo 1/2010, Ley 5/2024 deflactación)

Identical 2024 → 2025 → 2026:

| Base liquidable (€) | Tipo |
|---|---|
| 0 – 13.362,22 | 8,50% |
| 13.362,22 – 19.004,63 | 10,70% |
| 19.004,63 – 35.425,68 | 12,80% |
| 35.425,68 – 57.320,40 | 17,40% |
| 57.320,40 + | 20,50% |

#### Cataluña (Llei 5/2020 + actualizaciones)

| Base liquidable (€) | Tipo (2024-2026) |
|---|---|
| 0 – 12.450 | 10,50% |
| 12.450 – 17.707,20 | 12,00% |
| 17.707,20 – 21.000 | 14,00% |
| 21.000 – 33.007,20 | 15,00% |
| 33.007,20 – 53.407,20 | 18,80% |
| 53.407,20 – 90.000 | 21,50% |
| 90.000 – 120.000 | 23,50% |
| 120.000 – 175.000 | 24,50% |
| 175.000 + | 25,50% |

#### Andalucía (Decreto Legislativo 1/2018 modif.)

| Base liquidable (€) | Tipo (2024-2026) |
|---|---|
| 0 – 13.000 | 9,50% |
| 13.000 – 21.100 | 12,00% |
| 21.100 – 35.200 | 15,00% |
| 35.200 – 60.000 | 18,50% |
| 60.000 + | 22,50% |

#### Comunitat Valenciana (Ley 13/1997 modif. anual)

| Base liquidable (€) | Tipo (2024-2026) |
|---|---|
| 0 – 12.000 | 9,00% |
| 12.000 – 22.000 | 12,00% |
| 22.000 – 32.000 | 15,00% |
| 32.000 – 42.000 | 17,50% |
| 42.000 – 52.000 | 20,00% |
| 52.000 – 65.000 | 22,50% |
| 65.000 – 72.000 | 25,00% |
| 72.000 – 100.000 | 26,50% |
| 100.000 – 150.000 | 27,50% |
| 150.000 – 200.000 | 28,50% |
| 200.000 + | 29,50% |

#### Castilla y León (Decreto Legislativo 1/2013)

| Base liquidable (€) | Tipo (2024-2026) |
|---|---|
| 0 – 12.450 | 9,00% |
| 12.450 – 20.200 | 12,00% |
| 20.200 – 35.200 | 14,00% |
| 35.200 – 60.000 | 18,50% |
| 60.000 + | 21,50% |

The 10 remaining ordinary CCAAs each publish their own scale (rates
range 8-27% top). Implementation pulls each from the CCAA's vigent
texto refundido / Ley de Presupuestos at integration time.

### 6.4 2026 verifiability — most CCAAs unpublished at retrieval

| CCAA | 2026 Ley | Status | Source |
|---|---|---|---|
| Andalucía | Ley 8/2025 PGCA 2026 | **PUBLISHED 2025-12-31 BOJA/BOE** | confirmed |
| Comunitat Valenciana | Ley 5/2025 medidas + Ley 6/2025 presupuestos | **PARTIAL** — only modificaciones puntuales | `BOE-A-2025-11959`, `BOE-A-2025-11960` |
| Madrid | Ley 5/2024 + actualizaciones | **PARTIAL** — tarifa estable; importes 2026 unverifiable | confirmed |
| Cataluña | Ley 8/2025 (estatuto municipios rurales) | **PARTIAL** — afecta sólo D.VIV_RURAL; full PGE 2026 unverifiable | confirmed |
| Aragón / Asturias / Baleares / Canarias / Cantabria / Castilla-La Mancha / Castilla y León / Extremadura / Galicia / Murcia / La Rioja | Ley de Presupuestos / Medidas 2026 | **unverifiable** at 2026-04-27 | pending |

**Implementation rule for 2026:** Use 2025 values as the 2026 baseline
with a per-deduction `validated_for_year` annotation. The
`legal_basis` citation for 2026-only rows includes the BOE consult-
date pin `&p=20260228&tn=1` and a docstring note that the value is
inherited from 2025 pending each CCAA's 2026 Ley publication. Any
post-publication delta lands as a follow-up `chore` issue.

### 6.5 Cached corpus — pre-existing AEAT manual práctico PDFs

The CCAA subagent noted the repository already carries:

- `corpus/manuals/renta/2025/parte2-deducciones-autonomicas/source.pdf`
  (sha256 verified) — AEAT 2025 deducciones autonómicas manual.

The 2024 equivalent is not cached but is fetchable from
`https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2024-Deducciones-autonomicas/ManualRenta2024Tomo2_es_es.pdf`.
Implementation will fetch and pin this fixture. The 2026 manual will
become available roughly Q2 2027.

## 7. Per-annum delta map (BOE primary-sourced)

The BOE primary-source research stream returned the following
authoritative anchors as of retrieval 2026-04-27. Every numerical value
below is cited to its BOE consolidated-text URL or modifying law.

### 7.1 Foundational laws (consolidated-text anchors)

| Source | Identifier | BOE id | Role |
|---|---|---|---|
| Ley 35/2006 LIRPF | LIRPF base | `BOE-A-2006-20764` | IRPF base law; arts. 17-101 frame the entire M100 surface |
| Ley 27/2014 LIS | LIS base | `BOE-A-2014-12328` | Amortization tables (art. 12), inventory (art. 17), libertad amort. PYMES (art. 102) |
| RD 439/2007 RIRPF | RIRPF base | `BOE-A-2007-6820` | IRPF reglamento; arts. 28-32 estimación directa simplificada + módulos, arts. 80-87 retenciones, arts. 109-112 pagos fraccionados, arts. 113-117 régimen Beckham |

### 7.2 Per-año Orden HAC (M100 form template)

| Ejercicio | Orden HAC | Fecha | BOE id | Status at 2026-04-27 |
|---|---|---|---|---|
| 2023 | HAC/265/2024 | 18 marzo 2024 | `BOE-A-2024-5721` | published |
| 2024 | HAC/242/2025 | 13 marzo 2025 | `BOE-A-2025-5049` | published (already cited in `src/aeat/domain/modelos/_entries/modelo_100.py`) |
| 2025 | HAC/277/2026 | 25 marzo 2026 | `BOE-A-2026-7041` | published |
| 2026 | not yet | — | — | **unverifiable**; precedent ~feb-mar 2027 |

### 7.3 Modifying laws — load-bearing for M100 2024-2026

| Law | BOE id | Effective from | Affects |
|---|---|---|---|
| RD-Ley 4/2024 | `BOE-A-2024-13066` | 1/1/2024 | LIRPF art. 20 reducción rendimientos del trabajo (new thresholds 14.852/17.673,52/19.747,50, max 7.302); LIRPF art. 96 obligación declarar elevado a 15.876 €; libertad amortización vehículos eléctricos DA 59ª; mecanismo autoliquidación rectificativa (casillas 669, 701) |
| Ley 7/2024 | `BOE-A-2024-26694` | 1/1/2025 | LIRPF art. 66 tarifa del ahorro: top bracket >300k cambia de 28% combinado (estatal 14%) a **30% combinado (estatal 15%)**; reducción 30% rendimientos artísticos excepcionales máx 150.000 € |
| Ley 12/2023 | `BOE-A-2023-12203` | contratos desde 26/5/2023 | LIRPF art. 23.2 reducción capital inmobiliario por vivienda — **tiered 50/60/70/90%** (no longer a flat 60%) |
| RD 142/2024 | `BOE-A-2024-2249` | 1/1/2024 | RIRPF arts. 80-87 retenciones — actualizadas para acomodar RD-Ley 4/2024 |
| Ley 28/2022 ("Ley de Startups") | `BOE-A-2022-22693` | 1/1/2023 | LIRPF art. 93 régimen Beckham — extendido a digital nomads, I+D, profesionales altamente cualificados, cónyuge + hijos <25 |
| Orden HAC/1425/2025 | `BOE-A-2025-25272` | 1/1/2026 | Módulos IRPF estimación objetiva ejercicio 2026 + régimen simplificado IVA |

### 7.4 Tarifa estatal general (LIRPF art. 63)

**Stable since 1/1/2021 (Ley 11/2020)** — identical for 2024, 2025, 2026.

| Base liquidable hasta (€) | Cuota íntegra (€) | Resto base hasta (€) | Tipo estatal % |
|---|---|---|---|
| 0 | 0 | 12.450 | 9,50 |
| 12.450 | 1.182,75 | 7.750 | 12,00 |
| 20.200 | 2.112,75 | 15.000 | 15,00 |
| 35.200 | 4.362,75 | 24.800 | 18,50 |
| 60.000 | 8.950,75 | 240.000 | 22,50 |
| 300.000 | 62.950,75 | en adelante | 24,50 |

### 7.5 Tarifa estatal del ahorro (LIRPF art. 66)

Year-delta on the top bracket via Ley 7/2024.

#### 2024

| Base ahorro hasta (€) | Tipo estatal % | Tipo combinado % |
|---|---|---|
| 6.000 | 9,50 | 19 |
| 50.000 | 10,50 | 21 |
| 200.000 | 11,50 | 23 |
| 300.000 | 13,50 | 27 |
| > 300.000 | 14,00 | **28** |

#### 2025 + 2026 (post Ley 7/2024)

| Base ahorro hasta (€) | Tipo estatal % | Tipo combinado % |
|---|---|---|
| 6.000 | 9,50 | 19 |
| 50.000 | 10,50 | 21 |
| 200.000 | 11,50 | 23 |
| 300.000 | 13,50 | 27 |
| > 300.000 | **15,00** | **30** |

### 7.6 Mínimo personal y familiar (LIRPF arts. 57-60)

**Stable since 2015** — identical for 2024, 2025, 2026.

| Concepto | Importe (€) | LIRPF art. |
|---|---|---|
| Mínimo del contribuyente (general) | 5.550 | 57 |
| + supplemento >65 | +1.150 | 57 |
| + supplemento >75 | +1.400 (sobre el >65) | 57 |
| Descendiente 1º | 2.400 | 58 |
| Descendiente 2º | 2.700 | 58 |
| Descendiente 3º | 4.000 | 58 |
| Descendiente 4º+ | 4.500 | 58 |
| + bonus <3 años | +2.800 | 58 |
| Ascendiente >65 ó discapacidad (rentas <8.000) | 1.150 | 59 |
| + supplemento ascendiente >75 | +1.400 | 59 |
| Discapacidad <65% | 3.000 | 60 |
| Discapacidad ≥65% | 9.000 | 60 |
| + gastos asistencia (ayuda terceros, movilidad reducida o ≥65%) | +3.000 | 60 |

Convivencia + rentas-de-perceptor <8.000 € as common requirements (LIRPF art. 61).

### 7.7 Reducción por rendimientos del trabajo (LIRPF art. 20, post RD-Ley 4/2024)

**Stable for 2024, 2025, 2026.**

| Tramo rendimiento neto previo (€) | Reducción (€) |
|---|---|
| ≤ 14.852 | 7.302 |
| 14.852 - 17.673,52 | 7.302 − 1,75 × (rendimiento − 14.852) |
| 17.673,52 - 19.747,50 | 2.364,34 − 1,14 × (rendimiento − 17.673,52) |
| > 19.747,50 | 0 |

Requisito común: otras rentas (excluidas exentas) ≤ 6.500 €.

### 7.8 Reducción por arrendamiento de vivienda habitual (LIRPF art. 23.2 — post Ley 12/2023)

| Reducción | Condición |
|---|---|
| 90% | nuevo contrato en zona mercado tensionado con reducción ≥5% sobre renta inicial del contrato anterior |
| 70% | primer alquiler en zona tensionada a inquilino 18-35; o arrendamiento a Administración Pública/entidad sin fines lucrativos para vivienda social |
| 60% | vivienda objeto de actuación de rehabilitación finalizada en los 2 años anteriores |
| 50% | resto de los casos (default) |

Aplica sobre rendimiento neto positivo declarado. Contratos celebrados desde 26/5/2023.

### 7.9 Régimen especial impatriados — Ley Beckham (LIRPF art. 93)

- Tipo fijo trabajo: 24% hasta 600.000 €; **47%** sobre exceso.
- Tipo aplicable a rendimientos del ahorro art. 25.1.f) LIRPF: escala de no residentes 19/21/23/27/30% (top sube de 28% a 30% desde 1/1/2025 vía Ley 7/2024).
- Duración: período cambio residencia + 5 ejercicios siguientes (6 años).
- Requisitos: no residente fiscal en España en los 5 ejercicios previos.
- Ampliaciones por Ley 28/2022: digital nomads, I+D+i (>40% rendimientos), profesionales altamente cualificados, cónyuge e hijos <25 (o discapacidad sin límite).

### 7.10 Estimación directa simplificada (RIRPF art. 30)

Gastos de difícil justificación: **5%** del rendimiento neto positivo, con cap anual **2.000 €**. Encoding: `min_op(percent(0.05, rendimiento_neto_pos), lit("2000.00"))`. **Stable for 2024, 2025, 2026.**

### 7.11 LIS art. 12.1.a) — tabla de amortización lineal

Authoritative table (LIS Ley 27/2014). Aplicable a actividades económicas IRPF en estimación directa normal (LIRPF art. 28). Columns: max coeficiente lineal (%), max período (años).

| Categoría | Subcategoría | Coef max % | Período max años |
|---|---|---|---|
| Obra civil | general | 2 | 100 |
| | pavimentos | 6 | 34 |
| | infraestructuras y obras mineras | 7 | 30 |
| Centrales | hidráulicas | 2 | 100 |
| | nucleares | 3 | 60 |
| | de carbón | 4 | 50 |
| | renovables | 7 | 30 |
| | otras | 5 | 40 |
| Edificios | industriales | 3 | 68 |
| | escombreras (terrenos) | 4 | 50 |
| | almacenes y depósitos | 7 | 30 |
| | comerciales / administrativos / servicios / viviendas | 2 | 100 |
| Instalaciones | subestaciones / redes transporte y distribución | 5 | 40 |
| | cables | 7 | 30 |
| | resto instalaciones | 10 | 20 |
| Maquinaria | general | 12 | 18 |
| | equipos médicos | 15 | 14 |
| Transporte | locomotoras / vagones / tracción | 8 | 25 |
| | buques / aeronaves | 10 | 20 |
| | transporte interno | 10 | 20 |
| | transporte externo | 16 | 14 |
| | autocamiones | 20 | 10 |
| Mobiliario | mobiliario | 10 | 20 |
| | lencería | 25 | 8 |
| | cristalería | 50 | 4 |
| | útiles y herramientas | 25 | 8 |
| | moldes / matrices / modelos | 33 | 6 |
| | otros enseres | 15 | 14 |
| Electrónica | equipos electrónicos | 20 | 10 |
| | equipos tratamiento información | 25 | 8 |
| | sistemas y programas informáticos | 33 | 6 |
| Producciones | cinematográficas / fonográficas / audiovisuales | 33 | 6 |
| Otros | otros elementos | 10 | 20 |

Métodos alternativos al lineal: porcentaje constante (1,5×–2,5× lineal), suma de dígitos, plan formulado contribuyente aprobado, justificación específica (LIS arts. 12.1.b-e). Libertad de amortización: LIS arts. 12.3 + 102 (PYMES, I+D, vehículos eléctricos por DA 18ª LIS via Ley 31/2022 + DA 59ª LIRPF post RD-Ley 4/2024).

LIS art. 17 inventario: permite valoración por coste adquisición/producción, **precio medio o coste medio ponderado**, y **FIFO**. **LIFO no admitido**.

RD 634/2015 (Reglamento del IS, `BOE-A-2015-7771`) NO duplica la tabla — la tabla oficial reside en el art. 12.1.a) LIS.

### 7.12 2026 unverifiable surface — flagged

A 2026-04-27 los valores siguientes NO están confirmados por norma BOE
posterior a 2025-12-31:

- **Orden HAC del Modelo 100 ejercicio 2026** — no publicada (precedente: feb-mar 2027).
- **Modificación de la escala general estatal (art. 63) para 2026** — no localizable. PGE 2026 en prórroga al cierre Q1 2026.
- **Ajuste por inflación del mínimo personal (arts. 57-60) para 2026** — no localizable. Cifras siguen las de 2015.
- **Modificaciones tarifa del ahorro (art. 66) para 2026** — no localizables. Sigue Ley 7/2024.
- **Ampliaciones régimen Beckham 2026** — sin novedad post-Ley 28/2022.
- **5% gastos difícil justificación (RIRPF art. 30) para 2026** — sin novedad. Sigue 5% con cap 2.000 €.

**Implementation rule:** El ruleset `modelo_100.2026` clona los valores
2025 con `effective_from`/`effective_to` 2026; cada citación 2026 se
ancla con `&p=20260228&tn=1` indicando consulta consolidada al
2026-02-28; cualquier valor que requiera Orden HAC 2026 specific se
defiere a follow-up issue cuando esa Orden se publique.

## 8. Architectural options for the ADR

The user's directive frames scope as unbounded; the implementation must
balance comprehensiveness against maintainability. Key decisions for
the ADR:

### D1. File layout — flat per year vs. per-anexo modules per year

Option A: One file per year (`modelo_100_2024.py`, `_2025.py`, `_2026.py`)
mirroring sibling Tier-L pattern but at far larger size — likely
2000-4000 lines per file. Pros: uniform with M115/M123/M130/M131/M111;
easy to grep. Cons: file size; rebase friction; hard to delegate
sub-anexo authoring.

Option B: Per-anexo sub-modules per year, e.g.
`modelo_100/_anexo_a_2025.py`, `_anexo_b1_2025.py`, ..., aggregated in
`modelo_100/__init__.py` per year. Pros: scales to 9 anexos × 3 years
= 27 files; each file modest size; per-anexo PR review tractable. Cons:
deviates from sibling pattern; introduces a sub-package within
`_rulesets/` which has no precedent.

**Recommendation: B (per-anexo sub-modules per year)** — at M100 scale
the flat file approach exceeds reasonable review size, and the
sub-package pattern is forward-looking for the eventual full-RENTA
universe. The ADR will pin this.

### D2. Per-CCAA modeling — 17 separate modules vs. shared module + parameter table

Option A: 17 per-CCAA modules per year (`anexo_n_andalucia_2025.py`,
`anexo_n_aragon_2025.py`, ...) totalling 17 × 3 = 51 modules just for
Anexo Ñ.

Option B: One shared `anexo_n_2025.py` per year with `ParameterTable`
keyed by `<ccaa>.<deduction_id>`, and a closed `CCAA` `StrEnum` that
the formula DSL resolves at audit time. Caller supplies CCAA context
on `Filing`.

**Recommendation: B (shared module + parameter table)** — fits
naturally with the existing `ParameterTable` shape and avoids 51-file
explosion. Risk: per-CCAA deductions are heterogeneous (variable
constraints — e.g. nacimiento amount depends on número orden + edad
descendiente + renta familiar threshold), so each deduction may need
its own formula module under Anexo Ñ. Mixed: shared `_ANEXO_N` module
hosts every deduction's formula, but parameter values per CCAA per año
keyed by enum.

### D3. Amortization table representation

Option A: `ParameterTable` entries keyed `lis.amort.<asset_class>.coef`
and `lis.amort.<asset_class>.years`. Each asset class has 2 entries.
Closed `AssetClass` `StrEnum`.

Option B: Pydantic `AmortizationTable` model with explicit
`{asset_class: (coef, max_years)}` mapping, validated at module load.
Frozen.

**Recommendation: B (Pydantic model)** — the LIS art. 12 table is a
tightly-bounded data structure; Pydantic discipline + closed enum
keeps it self-documenting and type-safe.

### D4. Inventory valuation model

Option A: `ParameterTable` entries per actividad económica.
Option B: Pydantic `InventoryRecord(method: ValuationMethod, initial:
Decimal, final: Decimal)` per actividad, where `ValuationMethod` is a
closed `StrEnum` (FIFO / PMP / COSTE_MEDIO).

**Recommendation: B** — same reasoning as D3; data structure deserves
explicit typing.

### D5. Per-régimen split for Anexo D

Option A: One Anexo D module covering all 3 régimenes via conditional
casilla activation.
Option B: Three sub-modules — `anexo_d_directa_normal_<año>.py`,
`anexo_d_directa_simplificada_<año>.py`, `anexo_d_modulos_<año>.py`.

**Recommendation: B** — mirrors the BOE template structure where
distinct casillas appear per régimen; avoids cross-régimen casilla
collision.

### D6. Round-trip strategy for multi-anexo M100

The existing `Modelo100GenParams` carries `casilla_values: Mapping[str,
Decimal]` flexibly. The full-form generator extends this same flexibility
without breaking the existing M100 summary path. Per the borrador
dispatch, the synthetic generator emits a multi-anexo PDF that the
borrador extractor (extended) parses. Round-trip:
`generator(params) → PDF → borrador extractor → casilla map ==
expected_casillas`.

### D7. L1 anchor strategy

M100 declaraciones are publicly visible in AEAT instruction PDFs and
training materials. The 2026-04-21 ADR identifies Renta Web Open as a
free anonymous simulator yielding "vista previa" PDFs — the canonical
L1 source. Target: ≥ 5 Renta-Web-Open anchors per año covering distinct
life shapes (employee single / employee married with kids / autónomo
E.D. simplificada / autónomo E.D. normal / autónomo módulos / capital
inmobiliario heavy / ganancias patrimoniales heavy).

### D8. Cent-exact rounding policy

Same as sibling Tier-L: every `formula()` body wraps in terminal
`RoundFormula(digits=2, ROUND_HALF_UP)`. No intermediate rounding.
Division uses `quantize="0.0001"` four-decimal precision before the
2dp terminal. Tolerance for engine audit = `Decimal("0.01")`.

### D9. Multi-agent review wave plan

Per user directive — gemini-code-assist (auto on draft PR), codex
review subagent, claude review subagent (or `vaultspec-code-reviewer`).
Trigger after waves 5 (first complete anexo), 7 (Anexo D), 9 (Anexo Ñ),
final. Each review's findings captured in per-wave exec record.

### D10. Rolling audit checkpoints

After each implementation wave: `aeat audit rulesets citations` 100%;
`just lint && just typecheck && just hooks` green;
`just test src/aeat/domain/formulas/_rulesets/test_modelo_100*` green;
mutation kill-rate ≥ 90% on newly-added M100 nodes; per-wave exec
record captures audit results.

## 9. Open questions for the ADR

1. **Sub-package precedent.** No `_rulesets/` sub-package exists today.
   ADR D1 introduces one. Confirm with the user / sibling reviewer that
   `src/aeat/domain/formulas/_rulesets/modelo_100/` as a sub-package is
   acceptable, or fall back to flat-per-year.
2. **Per-CCAA scope discipline.** The original `#317` issue body
   permitted "either all 17 CCAA or Kent's declared CCAA only with
   waiver". The megaproject directive expands to all 17. Verify no
   stakeholder pushback on landing 17 × 3 = 51 (CCAA × año) deduction
   sets in one PR.
3. **Régimen objetiva (módulos) coverage depth.** Module 131 already
   models módulos for self-employed activities. M100 Anexo D módulos
   shares the Orden HAC tabla. Decide: re-model the tabla in M100
   (duplication risk) or share via parameter import from M131 module
   (coupling risk).
4. **Pre-2020 RENTA template support.** The 2026-04-21 ADR scoped
   2020+ only (XFA limitation pre-2020). Confirm 2024/2025/2026 are
   the only years in scope; 2020-2023 are existing declaración parser
   territory and not covered by the new full-form rulesets.
5. **Live AEAT interaction.** **HARD STOP** — live submission is
   permanently forbidden per `#432`. M100 work touches verification
   only.

## 10. Implementation patterns to mirror — quick reference card

When authoring `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_<X>_<año>.py`:

1. Module docstring narrating year-delta vs. prior año + scope.
2. `_label(es, en, hu)` private helper.
3. `_CITATIONS_<ANEXO>` tuple — each `make_citation` carries BOE URL
   with `&p=YYYYMMDD&tn=1` consolidated-text date pin.
4. `_CASILLAS_<ANEXO>` tuple — `casilla()` per cell; `legal_basis=...`
   on every `computed=True`.
5. `_FORMULAS_<ANEXO>` tuple — `formula(casilla_id, formula_id, body)`
   with `formula_id="modelo_100.<año>.<reason>"`.
6. `_PARAMETERS_<ANEXO>` `ParameterTable` keyed by `<anexo>.<reason>`
   with `effective_from`/`effective_to` per-año bounds.
7. Aggregate per-año `modelo_100/__init__.py` builds the `RULESET`
   `Ruleset(...)` constant from union of all anexos.
8. Test file co-located: `test_anexo_<X>_<año>.py` with module-level
   `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`,
   external-anchored worked examples per BOE article, threshold-edge,
   zero-boundary, per-año regression.
9. Mutation harness EXPECTED_COUNTS bumped for M100 per año.
10. Citation audit + lint/typecheck/test green before commit.
11. Conventional commit:
    `feat(rulesets/m100): anexo X for year YYYY (BOE primary-sourced) (#317)`.

## 11. Out of scope (hard exclusions)

- Foral regimes (País Vasco / Navarra) — `#424`.
- Tier-S / Tier-R modelos.
- IVA umbrella `#345`.
- Modifications to `aeat.adapters.persistence.storage` / `aeat.domain.financial` (`#216`).
- Any new CLI commands beyond `aeat audit rulesets citations`.
- Live AEAT submission (permanently forbidden per `#432`).
- Pre-2020 RENTA XFA template support.
- Renta rectificativa flow.
