---
tags:
  - '#exec'
  - '#modelo-100-renta-full-calc'
date: '2026-04-28'
modified: '2026-06-13'
related:
  - "[[2026-04-27-modelo-100-renta-full-calc-plan]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-research]]"
---



# `modelo-100-renta-full-calc` wave 5 — anexo-b1-rendimientos-del-trabajo

Wave 5 of the megaproject implementation per the parent plan: sub-package
scaffolding plus Anexo B1 (rendimientos del trabajo) for ejercicios
2024 / 2025 / 2026, including the LIRPF art. 20 piecewise reducción
encoded via the `max_op(piece_a, piece_b)` DSL pattern.

This wave is the "first complete anexo" milestone the plan flagged as
the trigger for opening the draft PR. With this wave landed locally,
the architecture (sub-package, per-anexo per-año module split, Pydantic
amortización + inventario, closed CCAA enum) is validated end-to-end
and subsequent anexos plug into the same shape.

## Files created

- Sub-package scaffolding:
    - `src/aeat/domain/formulas/_rulesets/modelo_100/__init__.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/_common.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/_ccaa.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/_amortization.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/_inventario.py`
- Per-anexo per-año:
    - `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_b1_2024.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_b1_2025.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_b1_2026.py`
- Per-año aggregators:
    - `src/aeat/domain/formulas/_rulesets/modelo_100_2024.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100_2025.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100_2026.py`
- Co-located tests:
    - `src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_b1_2024.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_b1_2025.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_b1_2026.py`

## Files modified

- `src/aeat/domain/formulas/_rulesets/__init__.py` — registered
  `MODELO_100_2024 / 2025 / 2026` (default variant) alongside the
  existing `MODELO_100_SUMMARY_2025`. Updated docstring with the
  megaproject `#317` overview.
- `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py` — bumped
  `EXPECTED_COUNTS` for the three new rulesets (sub_op=9,
  mul_div_scalar=2 per ruleset; no PercentFormula or BracketsFormula
  nodes yet).
- `src/aeat/domain/formulas/_rulesets/test_zero_boundary_coverage.py` —
  parametrize list extended with the three new rulesets; secondary-
  guard skip-list extended with `0021` (M100 art. 20 reducción cap
  is 7.302 € constant for rendimientos ≤ 14.852, so non-zero on zero
  input — by-design skip mirrors the M303 rate-literal pattern).

## Description

The sub-package layout follows the ADR D1 commitment: `modelo_100/`
hosts the per-anexo per-año modules plus shared helpers, while the
per-año aggregators (`modelo_100_2024.py / 2025.py / 2026.py`) live at
the parent `_rulesets/` level mirroring the sibling Tier-L pattern.
Each aggregator imports its anexo's `CASILLAS / FORMULAS / PARAMETERS /
CITATIONS` exports and composes them into the public `RULESET`
constant.

The Anexo B1 ruleset covers eight casillas: 0001 (ingresos íntegros),
0008 (cotización SS), 0009 (otros gastos), 0010 (movilidad geográfica),
0019 (reducción art. 18 30 % irregulares — caller-supplied), 0020
(rendimiento neto previo, computed), 0021 (reducción art. 20,
computed), 0022 (rendimiento neto reducido, computed). The art. 20
piecewise reducción is encoded as `max_op(piece_a, piece_b)` where
each piece is `clamp_pos(7302 - 1.75 * clamp_pos(rendimiento - 14852))`
or `clamp_pos(2364.34 - 1.14 * clamp_pos(rendimiento - 17673.52))`.
`max_op` selects the active piece at every rendimiento level; the
extrapolation tails clamp to zero. Verified cent-exact at six anchor
points (0 / 10.000 / 14.852 / 17.673,52 / 18.000 / 19.747,50 /
25.000 €).

The `_amortization.py` module encodes the LIS art. 12.1.a) lineal
table verbatim — 33 asset-class rows with their max coeficiente and
period. The `_inventario.py` module encodes ValuationMethod as a
closed enum (FIFO / PMP / COSTE_MEDIO; LIFO forbidden by construction
per LIS art. 17.6). The `_ccaa.py` module declares the 15-CCAA closed
enum (excluding País Vasco / Navarra foral regimes). These models
land here ahead of their consumer waves so the sub-package's data
foundations are stable before later waves plug into them.

The 2024 and 2026 Anexo B1 modules are structural clones of 2025 —
they import CASILLAS + CITATIONS from the 2025 reference module and
declare only their own FORMULAS (year-scoped formula IDs) plus
EFFECTIVE_FROM / EFFECTIVE_TO date constants. LIRPF arts. 17-20 are
stable across 2024 → 2025 → 2026 per BOE consolidated text consult
2026-02-28 (RD-Ley 4/2024 set the values for 2024; no posterior law
modified arts. 17-20). The 2026 ruleset's docstring documents that
the 2026 Orden HAC del Modelo 100 has not yet been published at
retrieval 2026-04-27 (precedent: feb-mar 2027) and any 2026-specific
delta lands as a follow-up issue.

## Audit checkpoint (rolling per the plan)

- `aeat audit rulesets citations` — 100 % coverage on every M100
  ruleset (existing summary 4/4, new 2024 3/3, new 2025 3/3, new 2026
  3/3).
- `just lint` — clean.
- `just typecheck` (`ty check src tests`) — clean.
- `just hooks` (prek run --all-files) — clean.
- `pytest src/aeat/domain/formulas/_rulesets/` — 464 tests pass (24 new
  Anexo B1 cases plus harness extensions).
- Mutation harness — `EXPECTED_COUNTS` bumped; per-class harnesses
  (operand-swap, scalar, kill-rate aggregator, exhaustiveness defense)
  all pass on the three new rulesets without manual registration.
- Zero-boundary harness — three new rulesets added; M100 0021 by-
  design non-zero constant skipped via the same pattern M303 uses for
  its rate-literal casillas.

## Tests

24 new test cases across three Anexo B1 test files:

- 8-case parametrized piecewise art. 20 anchor (zero / below cap /
  cap / mid piece-a / piece-a-piece-b boundary / mid piece-b / piece-b
  zero / above cap).
- Consistent-filing smoke + zero-boundary + clamp-negative + drift
  detection on 0020 and 0021 + ruleset shape + external-anchored
  worked example pinned to LIRPF art. 20 post RD-Ley 4/2024.
- 2024 / 2026 parity tests + 2026-vs-2025 no-drift regression.

## Out of scope for this wave

Anexo A (datos personales) is not part of the formula DSL surface —
it is metadata on the `BorradorFiling` record (NIF, civil status,
descendientes count, CCAA tax residence) consumed by later anexos to
parameterize their formulas. No casillas are added for Anexo A; the
plan's Wave 5 task list is updated to reflect this.

The art. 19 supplemento de 2.000 € otros gastos cap (LIRPF art. 19.2)
is not yet enforced as a formula constraint — for this wave casilla
0009 is a caller-supplied input. Constraint enforcement waits for a
DSL extension (the current DSL has no general "cap at parameter"
operator beyond `min_op` with literal). Tracked as a known limitation
in the rule-delta reference manifest.

## Wave 6 — Anexos B2 (capital mobiliario) + C (capital inmobiliario)

Landed in the same session as Wave 5; the per-año aggregator now
composes B1 + B2 + C into 23 casillas / 7 computed / 7 formulas across
each of 2024 / 2025 / 2026.

### Files created

- Anexo B2 (capital mobiliario):
    - `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_b2_2024.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_b2_2025.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_b2_2026.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_b2_2025.py`
- Anexo C (capital inmobiliario):
    - `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_c_2024.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_c_2025.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_c_2026.py`
    - `src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_c_2025.py`

### Files modified

- `src/aeat/domain/formulas/_rulesets/modelo_100_2024.py / _2025.py / _2026.py`
  per-año aggregators extended to compose Anexo B2 + C alongside the
  existing Anexo B1.
- `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py` —
  `EXPECTED_COUNTS` bumped (sub_op 9 -> 14 per ruleset; mul_div_scalar
  unchanged at 2). The five additional sub_ops are 2 in B2 (one in
  the rendimiento neto previo aggregation, one in the reducción
  art. 26.2 application) and 3 in C (two in the rendimiento neto
  previo nested chain `0061 - 0066 - 0072`, one in the reducción
  art. 23.2 application).
- B1 ruleset-shape tests updated from strict-equality on the computed
  set to subset assertion (since the aggregator now also carries B2
  and C casillas alongside B1).

### Anexo B2 description

LIRPF arts. 25-26 + 101.4 + RIRPF art. 90 anchors. Eight casillas:

- Inputs: 0028 dividendos, 0029 intereses cuentas, 0030 intereses
  títulos, 0031 otros, 0032 reducción art. 26.2 30 % irregularidad
  (caller-supplied), 0035 gastos administración / custodia.
- Computed: 0048 rendimiento neto previo capital mobiliario =
  `clamp_pos(0028 + 0029 + 0030 + 0031 - 0035)`, 0049 rendimiento
  neto reducido = `clamp_pos(0048 - 0032)`.

The `clamp_pos` on 0048 protects against the (rare) case where gastos
administración exceed total ingresos. The 0032 caller-supplied input
encodes the LIRPF art. 26.2 30 % over irregularidad already minorada,
mirroring the Anexo B1 art. 18 pattern.

### Anexo C description

LIRPF arts. 22-24 + 85 anchors. Seven casillas. The Ley 12/2023 tiered
reducción art. 23.2 (50 / 60 / 70 / 90 % depending on contract metadata)
is encoded as a caller-supplied tier amount in casilla 0078 — the DSL
lacks conditional logic and the tier selection requires inspection of
contract metadata (date, zona tensionada flag, inquilino age,
rehabilitación recency, reducción vs prior contract) that lives outside
the formula layer. The aggregation chain:

- 0106 (rendimiento neto previo) =
  `clamp_pos(0061 - 0066 - 0072)`
- 0107 (rendimiento neto reducido) =
  `clamp_pos(0106 - 0078)`

LIRPF art. 85 imputación de rentas inmobiliarias (1,1 % / 2 % del
valor catastral) is encoded as casilla 0085 — a parallel income line
that does NOT feed into 0106 / 0107. Anexo F (Wave 8) will consume
0085 directly into the base imponible general.

### Wave 6 audit checkpoint

- ✅ `aeat audit rulesets citations` — 100 % on every M100 ruleset
  (existing summary 4/4, new 2024 7/7, 2025 7/7, 2026 7/7).
- ✅ `just lint` — clean.
- ✅ `just typecheck` — clean.
- ✅ `just hooks` — clean.
- ✅ `pytest src/aeat/domain/formulas/_rulesets/` — 474 tests pass (10 new
  Anexo B2/C cases on top of the prior 464).
- ✅ Mutation kill-rate aggregator + operand-swap + zero-boundary +
  exhaustiveness defense pass on the three updated rulesets.

### Tests added

- 4 cases for Anexo B2 (consistent filing, irregularity reduction,
  gastos exceed ingresos clamp-to-zero, drift detection on 0048).
- 6 cases for Anexo C (default 50 % tier, zona tensionada 70 %, max
  90 %, negative arrendamiento clamps to zero, imputación parallel
  income separation, drift detection on 0107).

### Design notes for review

- The fixture helpers `_b2_zero_b1_c()` and `_c_zero_b1_b2()` zero out
  every other anexo's casillas so the focused tests don't depend on
  cross-anexo state. Casilla 0021 is set to 7.302 € (the by-design
  non-zero LIRPF art. 20 cap on zero rendimiento) since 0021 is
  always derived non-zero — engine would otherwise flag 0 vs 7.302
  drift.
- Imputación rentas inmobiliarias (LIRPF art. 85) lands in Anexo C
  as casilla 0085 even though it does not feed the aggregation chain.
  This keeps the Anexo C surface complete and gives Anexo F a clean
  reference target when it consumes the imputación into base
  imponible general.

### Next wave

Wave 7 — Anexo D (actividades económicas) for 2024 / 2025 / 2026. The
biggest single wave: three sub-modules per año (E.D. normal /
simplificada / módulos), inventory + amortización integration via the
existing `_amortization.py` and `_inventario.py` foundations, RIRPF
art. 30 5 %/2.000 € cap on simplificada gastos de difícil
justificación. Multi-agent review pass triggered after Wave 7 lands
per the ADR D11 plan.
