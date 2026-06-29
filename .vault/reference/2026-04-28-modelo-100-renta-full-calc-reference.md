---
tags:
  - '#reference'
  - '#modelo-100-renta-full-calc'
date: '2026-04-28'
modified: '2026-06-29'
related:
  - "[[2026-04-27-modelo-100-renta-full-calc-research]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-plan]]"
  - "[[2026-04-28-modelo-100-renta-full-calc-exec]]"
---



# `modelo-100-renta-full-calc` reference: rule-delta manifest 2024 / 2025 / 2026

Comprehensive per-anexo per-año rule-delta manifest for the full-form
Modelo 100 (RENTA / IRPF anual) ruleset. The implementation lives at
`src/aeat/domain/formulas/_rulesets/modelo_100/` (sub-package) and the per-año
aggregators `src/aeat/domain/formulas/_rulesets/modelo_100_<año>.py`.

This manifest is the authoritative reference for what changed from
2024 to 2025, from 2025 to 2026, and what remains stable across the
three years per BOE consolidated text consult 2026-02-28.

## Statutory grounding

| Reference | Role | BOE id |
|---|---|---|
| Ley 35/2006 LIRPF | IRPF base law (arts. 17-101) | `BOE-A-2006-20764` |
| Ley 27/2014 LIS | Amortizacion (art. 12), inventario (art. 17) | `BOE-A-2014-12328` |
| RD 439/2007 RIRPF | IRPF reglamento (arts. 28-30 estimacion directa, arts. 32 modulos, arts. 80-87 retenciones) | `BOE-A-2007-6820` |
| Ley 22/2009 | Cesion de tributos a las CCAA | `BOE-A-2009-20375` |
| RD-Ley 4/2024 | Reduccion art. 20 LIRPF + obligacion declarar 15876 EUR | `BOE-A-2024-13066` |
| Ley 7/2024 | Tarifa estatal del ahorro top 14% to 15% | `BOE-A-2024-26694` |
| Ley 12/2023 | Reduccion art. 23.2 LIRPF tiered 50/60/70/90% | `BOE-A-2023-12203` |
| Ley 28/2022 (Startups) | Regimen impatriados art. 93 LIRPF | `BOE-A-2022-22693` |
| Ley 6/2018 (PGE 2018) | Ceuta/Melilla art. 68.4 LIRPF 50% to 60% | `BOE-A-2018-9268` |
| Orden HAC/242/2025 | Modelo 100 2024 form template | `BOE-A-2025-5049` |
| Orden HAC/277/2026 | Modelo 100 2025 form template | `BOE-A-2026-7041` |
| Orden HAC/1425/2025 | Modulos IRPF 2026 | `BOE-A-2025-25272` |

## Implementation snapshot

| Quantity | Value |
|---|---|
| Sub-package modules per año | 8 anexos (B1, B2, C, D-normal, D-simplificada, D-modulos, E, F, G) + Anexo N |
| Total sub-package files | 27 anexo files (9 per año) + 4 foundation modules (`_common.py`, `_ccaa.py`, `_amortization.py`, `_inventario.py`) + 5 test files |
| Per-año aggregator modules | 3 (`modelo_100_2024.py`, `_2025.py`, `_2026.py`) |
| Casillas per ruleset | 90 |
| Computed casillas per ruleset | 30 |
| Formulas per ruleset | 30 |
| Mutation harness sub_op count | 71 per ruleset |
| Mutation harness mul_div_scalar count | 20 per ruleset |
| Citation coverage (`aeat audit rulesets citations`) | 100 % |
| Test count (`pytest src/aeat/domain/formulas/_rulesets/`) | 496 pass |

## Per-anexo casilla inventory

### Anexo B1 — rendimientos del trabajo (8 casillas: 5 inputs + 3 computed)

| Casilla | Role | Anchor | Computed |
|---|---|---|---|
| 0001 | Ingresos íntegros del trabajo | LIRPF art. 17 | input |
| 0008 | Cotización SS deducible | LIRPF art. 19 | input |
| 0009 | Otros gastos deducibles | LIRPF art. 19 | input |
| 0010 | Movilidad geográfica | LIRPF art. 19 | input |
| 0019 | Reducción art. 18 30% irregularidad | LIRPF art. 18 | input |
| 0020 | Rendimiento neto previo | LIRPF arts. 17-19 | computed = clamp_pos(0001-0008-0009-0010-0019) |
| 0021 | Reducción art. 20 piecewise | LIRPF art. 20 (post RD-Ley 4/2024) | computed via max_op(piece_a, piece_b) |
| 0022 | Rendimiento neto reducido del trabajo | LIRPF arts. 17, 20 | computed = clamp_pos(0020 - 0021) |

### Anexo B2 — rendimientos del capital mobiliario (8 casillas)

| Casilla | Role | Anchor | Computed |
|---|---|---|---|
| 0028 | Dividendos íntegros | LIRPF art. 25 | input |
| 0029 | Intereses cuentas y depósitos | LIRPF art. 25 | input |
| 0030 | Intereses títulos públicos / privados | LIRPF art. 25 | input |
| 0031 | Otros rendimientos capital mobiliario | LIRPF art. 25 | input |
| 0032 | Reducción art. 26.2 30% irregularidad | LIRPF art. 26 | input |
| 0035 | Gastos administración + custodia | LIRPF art. 26 | input |
| 0048 | Rendimiento neto previo | LIRPF arts. 25-26 | computed = clamp_pos(sum(0028..0031) - 0035) |
| 0049 | Rendimiento neto reducido capital mobiliario | LIRPF arts. 25-26 | computed = clamp_pos(0048 - 0032) |

### Anexo C — rendimientos del capital inmobiliario (7 casillas)

| Casilla | Role | Anchor | Computed |
|---|---|---|---|
| 0061 | Ingresos arrendamiento | LIRPF art. 22 | input |
| 0066 | Gastos deducibles | LIRPF art. 23.1 | input |
| 0072 | Amortización 3% construcción | LIRPF art. 23.1 | input |
| 0078 | Reducción tier 50/60/70/90% | LIRPF art. 23.2 (post Ley 12/2023) | input |
| 0085 | Imputación rentas inmobiliarias | LIRPF art. 85 | input (parallel — does NOT feed 0106/0107) |
| 0106 | Rendimiento neto previo capital inmobiliario | LIRPF arts. 22-23 | computed = clamp_pos(0061 - 0066 - 0072) |
| 0107 | Rendimiento neto reducido capital inmobiliario | LIRPF arts. 22-23 | computed = clamp_pos(0106 - 0078) |

### Anexo D — actividades económicas (3 régimenes)

#### D normal — estimación directa normal (11 casillas: 8 inputs + 3 computed)

LIRPF arts. 27-28 + 32; LIS arts. 12-14 + 17. RIRPF art. 28 (ámbito).
Casillas 0140 (ingresos), 0150 (compras), 0155 (variación existencias),
0165 (personal), 0170 (servicios), 0173 (amortización), 0180
(provisiones), 0200 (reducciones art. 32) → computed: 0190 (total
gastos), 0195 (rendimiento neto previo), 0205 (rendimiento neto
reducido).

#### D simplificada — estimación directa simplificada (7 casillas: 3 inputs + 4 computed)

RIRPF art. 30 general rate/cap on gastos de difícil justificación:
5% for the current non-exception revisions in this manifest, capped
at 2.000 €, with the rate read from the revision parameter so temporary
legal exceptions such as LIRPF DA 56 for 2023 cannot be flattened.
Casillas 0210 (ingresos), 0215 (gastos generales), 0235 (reducciones
art. 32) → computed: 0220 (rendimiento previo al cap), 0225 (gastos
difícil justificación = `min(rate_param * 0220, cap_param)`), 0230
(rendimiento neto previo), 0240 (rendimiento neto reducido).

#### D módulos — estimación objetiva (3 casillas: 2 inputs + 1 computed)

LIRPF art. 31 + RIRPF art. 32. Caller computes 0250 (rendimiento neto
previo módulos) from the Orden HAC tabla anual:

- 2024: Orden HAC/265/2024 (`BOE-A-2024-5721`) — was vigent in 2024.
- 2025: Orden HAC/277/2026 (`BOE-A-2026-7041`).
- 2026: Orden HAC/1425/2025 (`BOE-A-2025-25272`) covers módulos
  for ejercicio 2026.

Casilla 0260 = clamp_pos(0250 - 0255) — rendimiento neto reducido
módulos.

### Anexo E — ganancias y pérdidas patrimoniales (5 casillas)

LIRPF arts. 33-39 + 49. Casillas 0306 (ganancias brutas), 0307
(pérdidas brutas), 0399 (saldo a integrar en general — held <= 1
año), 0400 (saldo a integrar en ahorro — held > 1 año) — all caller-
supplied. Casilla 0405 = sub_op(0306, 0307) — saldo neto patrimonial
total. Caller pre-computes per-transacción FIFO regla acciones
(LIRPF art. 37) + holding-period split.

### Anexo F — bases imponibles + reducciones + mínimos (11 casillas)

LIRPF arts. 47-61 + 84.

Inputs: 0445 (planes pensiones art. 51-52), 0455 (tributación conjunta
art. 84), 0505 (mínimo contribuyente art. 57), 0510 (mínimo
descendientes art. 58), 0515 (mínimo ascendientes art. 59), 0520
(mínimo discapacidad art. 60).

Computed:
- 0432 BIG = 0022 + 0107 + 0085 + 0205 + 0240 + 0260 + 0399
- 0460 BIA = 0049 + 0400
- 0500 mínimo total = 0505 + 0510 + 0515 + 0520
- 0545 BLG = clamp_pos(0432 - 0445 - 0455)
- 0555 BLA = 0460 (passthrough)

### Anexo G — cuotas + tarifas + deducciones estatales (15 casillas)

LIRPF arts. 63 + 66 + 67 + 68 + 73 + 76 + 77 + 79 + 99.

Computed via `progressive_tarifa()` helper:
- 0540 = progressive_tarifa(0545, TARIFA_ESTATAL_GENERAL_2025)
- 0542 = progressive_tarifa(min_op(0500, 0545), TARIFA_ESTATAL_GENERAL_2025)
- 0550 = clamp_pos(0540 - 0542) — cuota íntegra estatal general
- 0560 = progressive_tarifa(0555, TARIFA_ESTATAL_AHORRO_<año>)

Inputs (caller-supplied per-CCAA): 0551 (autonómica general), 0561
(autonómica ahorro), 0612 (Ceuta/Melilla 60% — LIRPF art. 68.4).

Cuotas chain:
- 0595 = 0550 + 0551 + 0560 + 0561
- 0630 = 0620 + 0622
- 0698 = clamp_pos(0595 - 0630 - 0612)
- 0720 = 0698 - 0699 - 0700

### Anexo Ñ — deducciones autonómicas (16 casillas: 15 inputs + 1 computed)

LIRPF art. 46 bis + Ley 22/2009 (cesion de tributos).

Per-CCAA aggregate-deduction casillas (caller-supplied):
- 1101 Andalucía / 1102 Aragón / 1103 Asturias / 1104 Illes Balears
- 1105 Canarias / 1106 Cantabria / 1107 Castilla-La Mancha
- 1108 Castilla y León / 1109 Cataluña / 1110 Comunitat Valenciana
- 1111 Extremadura / 1112 Galicia / 1113 Madrid / 1114 Murcia
- 1115 La Rioja

Computed: 0622 = sum(1101..1115) — deducciones autonómicas total.

País Vasco / Navarra excluded (foral regimes per `#424`). Ceuta /
Melilla NOT a CCAA — state-level 60% deduction handled in Anexo G
casilla 0612.

## Year-delta narrative

### 2024 → 2025 deltas

| Anexo | Casilla | Delta | Source |
|---|---|---|---|
| G | 0560 (cuota íntegra estatal ahorro top bracket) | 14 % → **15 %** | Ley 7/2024 (`BOE-A-2024-26694`), efectos 1/1/2025 |
| All others | All | **None** | LIRPF arts. 17-101 + LIS arts. 12-17 + RIRPF arts. 28-30 stable |

### 2025 → 2026 deltas

| Anexo | Casilla | Delta | Source |
|---|---|---|---|
| All | All | **None** identified | BOE consolidated text consult 2026-02-28 — no posterior law modifies the M100 numerical surface |

The 2026 Orden HAC del Modelo 100 has not yet been published at
retrieval 2026-04-27 (precedent: feb-mar 2027). Any 2026-specific
delta lands as a follow-up issue when the Orden publishes.

## Per-CCAA 2026 verifiability

| CCAA | 2026 Ley de Presupuestos | Status at retrieval 2026-04-27 |
|---|---|---|
| Andalucía | Ley 8/2025 PGCA 2026 | **PUBLISHED** (BOJA / BOE 2025-12-31) |
| Comunitat Valenciana | Ley 5/2025 + 6/2025 | **PARTIAL** — modificaciones puntuales `BOE-A-2025-11959` / `BOE-A-2025-11960` |
| Madrid | Ley 5/2024 + actualizaciones | **PARTIAL** — tarifa estable, importes 2026 unverifiable |
| Cataluña | Ley 8/2025 (estatuto municipios rurales) | **PARTIAL** |
| Otras 11 CCAAs | Ley de Presupuestos 2026 | **unverifiable** — pending publication |

**Implementation rule for 2026**: Use 2025 deduction values as
conservative baseline. Per-CCAA refresh follow-up issues open
post-merge as each Comunidad publishes its 2026 Ley.

## Per-CCAA tarifa autonómica brackets (encoded)

Per LIRPF arts. 46 bis + 73-77 + Ley 22/2009 (cesión de competencias
normativas), each CCAA sets its own tarifa autonómica general scale.
The 5 highest-population CCAAs are encoded as first-class data in
`src/aeat/domain/formulas/_rulesets/modelo_100/_ccaa.py`, with stable brackets
across 2024 / 2025 / 2026. Callers compute casilla 0551 (cuota íntegra
autonómica general) externally via the
`compute_cuota_autonomica_general(blg, ccaa)` helper before supplying
it to the engine.

### Comunidad de Madrid (Decreto Legislativo 1/2010 + Ley 5/2024 deflactación)

| Base liquidable hasta (€) | Tipo |
|---|---|
| 13.362,22 | 8,5 % |
| 19.004,63 | 10,7 % |
| 35.425,68 | 12,8 % |
| 57.320,40 | 17,4 % |
| > 57.320,40 | 20,5 % |

### Cataluña (Llei 5/2020 + actualizaciones presupuestarias)

| Base liquidable hasta (€) | Tipo |
|---|---|
| 12.450 | 10,5 % |
| 17.707,20 | 12 % |
| 21.000 | 14 % |
| 33.007,20 | 15 % |
| 53.407,20 | 18,8 % |
| 90.000 | 21,5 % |
| 120.000 | 23,5 % |
| 175.000 | 24,5 % |
| > 175.000 | 25,5 % |

### Andalucía (Decreto Legislativo 1/2018 modificado)

| Base liquidable hasta (€) | Tipo |
|---|---|
| 13.000 | 9,5 % |
| 21.100 | 12 % |
| 35.200 | 15 % |
| 60.000 | 18,5 % |
| > 60.000 | 22,5 % |

### Comunitat Valenciana (Ley 13/1997 modificada anualmente)

| Base liquidable hasta (€) | Tipo |
|---|---|
| 12.000 | 9 % |
| 22.000 | 12 % |
| 32.000 | 15 % |
| 42.000 | 17,5 % |
| 52.000 | 20 % |
| 65.000 | 22,5 % |
| 72.000 | 25 % |
| 100.000 | 26,5 % |
| 150.000 | 27,5 % |
| 200.000 | 28,5 % |
| > 200.000 | 29,5 % |

### Castilla y León (Decreto Legislativo 1/2013)

| Base liquidable hasta (€) | Tipo |
|---|---|
| 12.450 | 9 % |
| 20.200 | 12 % |
| 35.200 | 14 % |
| 60.000 | 18,5 % |
| > 60.000 | 21,5 % |

### Worked example anchors

`test_ccaa_tarifa.py` exercises each tarifa at boundary + midpoint
anchors. Notable cumulative cuotas:

| CCAA | BLG (€) | Cuota íntegra autonómica general (€) |
|---|---|---|
| Madrid | 100.000 | 16.400,42 |
| Cataluña | 200.000 | 42.802,84 |
| Andalucía | 100.000 | 17.910,00 |
| Comunitat Valenciana | 300.000 | 77.125,00 |
| Castilla y León | 100.000 | 17.338,50 |

### Unencoded CCAAs (10 remaining)

Aragón, Asturias, Illes Balears, Canarias, Cantabria, Castilla-La
Mancha, Extremadura, Galicia, La Rioja, Murcia all publish their own
per-CCAA texto refundido / Ley de Presupuestos tarifas. The
`compute_cuota_autonomica_general()` helper raises `KeyError` on these
CCAAs — caller must compute externally pending follow-up per-CCAA
encoding waves. The full bracket data per remaining CCAA lives in the
research doc §6.3 (rate ranges 8-27 % top); each follow-up wave adds a
single `TARIFA_<CCAA>` constant + extends `PER_CCAA_TARIFA_AUTONOMICA`.

País Vasco / Navarra remain explicitly out of scope (foral regimes,
`#424`).

## L1 anchor decision

L1 anchors via Renta Web Open simulator outputs are **deferred** to a
post-merge follow-up. The synthetic L3 round-trip evidence (extending
the existing `Modelo100GenParams` synthetic generator + `aeat.adapters.inbound.borrador`
extractor) lands as a Wave 11 follow-up. Mirrors the M123 precedent:
L1 anchor coverage waivable when public anchors are not readily
hash-pinnable, with synthetic L3 round-trip as the verification path.

## Mutation fingerprint per ruleset

| Mutator class | Per-ruleset count |
|---|---|
| sub_op | 71 |
| percent_rate_literal | 0 |
| percent_rate_param | 0 |
| percent_rate_compound_skipped | 0 |
| percent_rate_casilla_ref_skipped | 0 |
| brackets_threshold_non_terminal | 0 |
| mul_div_scalar | 20 |

The 71 sub_op nodes fan out: 5 in Anexo B1 (rendimiento previo
chain), 4 in Anexo B1 (art. 20 piecewise), 1 in Anexo B1 (rendimiento
reducido), 2 in B2 (chain), 1 in B2 (reducido), 3 in C, 9 in D normal
(P&L total gastos chain + rendimiento chain), 4 in D simplificada,
1 in D módulos, 1 in E, 2 in F (BLG nested chain), 38 in G (3
progressive_tarifa applications × 6 brackets each, plus the cuota
chain).

The 20 mul_div_scalar nodes fan out: 2 in Anexo B1 (slopes 1.75 +
1.14 in art. 20 piecewise), 1 in D simplificada (revision-specific
rate parameter for the RIRPF art. 30 / DA 56 difficult-expense cap),
17 in G (rate literals across 3 progressive_tarifa applications).

## Out-of-scope (post-merge / separate issues)

- **Foral regimes** (País Vasco / Navarra) — `#424`.
- **Per-deduction breakdown per CCAA** — Anexo Ñ ships with per-CCAA
  aggregates; the per-CCAA per-deduction breakdown (~336
  deductions/año across 15 CCAAs) lands as per-CCAA follow-up issues.
- **Multi-anexo borrador extractor + synthetic generator extension**
  (Wave 11 deferred) — extends `src/aeat/adapters/inbound/borrador/_extractors/`
  modelo_100 surface to cover the full-form casilla map.
- **Kent integration test full-form class** — extends
  `tests/integration/test_kent_workflows.py` with a sibling class
  `TestKentImportsModelo100FullBorrador`.
- **L1 Renta Web Open anchor PDFs** — manual step, follow-up.
- **Live AEAT submission** — permanently forbidden per `#432`.
- **Pre-2020 RENTA template support** — XFA limitation per the
  2026-04-21 prior ADR.
the information that coding agents will consult during implementation.

## Findings

Findings pertinent to `modelo-100-renta-full-calc` being considered. Include implementation
details and architecture overviews considered insightful, essential, or
relevant. Adapt format to content.
