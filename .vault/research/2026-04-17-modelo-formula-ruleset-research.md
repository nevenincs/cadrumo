---
tags:
  - '#research'
  - '#modelo-formulas'
date: '2026-04-17'
modified: '2026-04-17'
related:
  - '[[2026-04-12-casilla-db-adr]]'
  - '[[2026-04-12-casilla-db-research]]'
  - '[[2026-04-13-modelo-inventory-adr]]'
  - '[[2026-04-13-modelo-inventory-research]]'
  - '[[2026-04-12-filing-draft-engine-adr]]'
  - '[[2026-04-12-base-module-structure-adr]]'
  - '[[2026-04-12-trilingual-i18n-adr]]'
---

# modelo-formulas research: per-modelo calculation formulas (casilla ruleset)

Foundational research for Issue #173 (domain: `local-state` + `mediation`).
Codifies the mathematical relationships between casillas (boxes) for AEAT
modelos. The proof-of-concept modelo is **Modelo 130** (IRPF pago fraccionado,
estimación directa). The research also specifies the engine-design space so
that the resulting `aeat.domain.formulas` subpackage extends cleanly to Modelo 303,
Modelo 100, and beyond.

Two research strands are captured here:

1. **AEAT domain research** — exact per-casilla calculation rules, period
   versioning, activity-combination logic, deducciones, and arrastre rules
   for Modelo 130 (2024 and 2025), with an explicit separation between
   AEAT-authoritative and 3rd-party-corroborative sources.
2. **Engine-design prior art** — evaluation of candidate architectures
   (pydantic-graph DSL vs. AST-whitelist vs. third-party evaluators like
   asteval/simpleeval/sympy), period-versioning patterns (OpenFisca),
   DAG topology (`graphlib.TopologicalSorter`), and Decimal discipline
   (ROUND_HALF_UP tax rounding).

Both strands feed the matching ADR
`[[2026-04-17-modelo-formulas-adr]]` and plan
`[[2026-04-17-modelo-formulas-plan]]`.

## Methodology

Primary AEAT / BOE sources (authoritative):

- AEAT "Instrucciones Modelo 130" on
  `sede.agenciatributaria.gob.es` —
  the canonical source of casilla labels, computed-vs-input tags, and
  the literal text of each rule.
- AEAT "Importe de los pagos fraccionados" on the same domain —
  confirmatory and contains the La Palma 60% reduction notice.
- BOE / AEAT-hosted consolidated PDFs of **Real Decreto 439/2007**
  (Reglamento IRPF), specifically `art. 110`, and **Ley 35/2006**
  (LIRPF), specifically `art. 99`.

Secondary 3rd-party corroboration (used only to reconstruct verbatim
article text when BOE PDFs were not plaintext-extractable):

- Iberley, SuperContable — consolidated legal texts for article
  reconstruction.
- Infoautónomos, Ayudatpymes, Quipu, Declarando, Cuéntica, Genealia,
  TeamSystem, Glasof, Anfix — tax-advisor guidance for edge cases and
  verification of minoraciones, vivienda-habitual gating, and the La
  Palma reduction.

Engine-design sources (all WebFetched; no library invoked on guesswork):

- asteval docs (lmfit.github.io/asteval, v1.0.8).
- simpleeval README (github.com/danthedeckie/simpleeval, v1.0.7).
- Python stdlib `graphlib.TopologicalSorter` reference.
- Python stdlib `decimal` reference.
- OpenFisca `coding-the-legislation` periods and parameters
  documentation.
- JSON Logic manifesto (jsonlogic.com).

Every finding is tagged *AEAT-primary* (authoritative) or
*3rd-party-secondary* (corroboration). No rule is committed to the ADR
without AEAT-primary backing.

## Landing zone audit (codebase integration surface)

The engine must integrate with three existing subpackages already
merged on `main`:

- **`aeat.domain.casillas`** — ships `CasillaCatalogue` (pydantic v2, frozen,
  strict), `CasillaRecord`, and a `FormulaReference` stub
  (`expression: str`, `references_casillas: tuple[str, ...]`). The
  `FormulaReference` was deliberately left as a placeholder for the
  #173 owner to replace with a strict, sandboxed representation. The
  canonical corpus lives at
  `corpus/casillas/<modelo>/<period>.json`; the existing corpus ships
  one period per modelo (`MODELO_130/2025Q4.json`,
  `MODELO_303/2025Q4.json`, `MODELO_390/2025.json`), each with a
  sample of computed casillas using free-form strings like
  `"0.20 * 01"` and `"max(0, 02 - 03)"`. These strings are
  **not executable anywhere today** — they exist to document intent
  and will be replaced by structured formula nodes.
- **`aeat.domain.modelos`** — ships the completed `ModeloCode` enum,
  `ModeloMetadata`, `MODELO_REGISTRY`, and `ModeloCadence` /
  `ModeloCategory` enums. Issue #108 landed on main via PR #135;
  the inventory is authoritative. The engine binds to `ModeloCode`
  and will never introduce its own modelo identifier.
- **`aeat.application.filing._builders.modelo_130`** — ships a **hardcoded**
  computation of Modelo 130 casillas (01–07) inside `Modelo130Builder`,
  explicitly described in its docstring as a stand-in until #9 lands
  a real formula AST. The hardcoded ids (01=ingresos, 02=gastos,
  03=01-02, 04=03×0.20, 05=retenciones, 06=anteriores,
  07=max(0, 04-05-06)) **do not match** the real AEAT Modelo 130
  casilla layout (01=ingresos, 02=gastos, 03=rendimiento neto,
  04=pago fraccionado, 05=pagos fraccionados anteriores,
  06=retenciones, 07=resultado parcial Ap. I …). The engine must
  replace this builder with a ruleset-driven equivalent and publish
  **the real 19-casilla Modelo 130**.

No change to `aeat.domain.portals` or `aeat.domain.deadlines` is in scope for #173.

## Modelo 130 — per-casilla formula reference (2024 and 2025)

All amounts are EUR with 2-decimal precision for published outputs and
4-decimal precision for intermediate computations. Rounding uses
`ROUND_HALF_UP` per Spanish accounting convention (see §Engine §3).
"Accumulated" means year-to-date from 1 January through the last day
of the reporting quarter, unless explicitly marked per-quarter
(casilla 08 and 10 are the only per-quarter exceptions).

The four quarters (periodos) are:

- 1T: Apr 1–20 (period covers Jan–Mar).
- 2T: Jul 1–20 (period covers Jan–Jun cumulative).
- 3T: Oct 1–20 (period covers Jan–Sep cumulative).
- 4T: Jan 1–30 of the following year (period covers the full
  prior year).

### Apartado I — Actividades económicas en estimación directa (distintas de las agrícolas, ganaderas, forestales y pesqueras)

**Casilla 01 — Ingresos**

- Official label: *"Totalidad de los ingresos íntegros fiscalmente
  computables procedentes del conjunto de sus actividades."*
- Type: EUR, user-entered.
- Required when Apartado I applies.
- Scope: cumulative YTD. Sign ≥ 0.
- Legal basis: RIRPF art. 110.1.a.

**Casilla 02 — Gastos**

- Official label: *"Gastos fiscalmente deducibles"*, including
  amortizaciones y provisiones deducibles. In estimación directa
  simplificada, the gastos de difícil justificación (5% cap + absolute
  annual cap per LIRPF art. 30.2.4ª + RIRPF art. 30) flow in through
  here.
- Type: EUR, user-entered. Sign ≥ 0. Scope: cumulative YTD.

**Casilla 03 — Rendimiento neto**

- Type: EUR, **computed**.
- **Formula:** `03 = 01 − 02`.
- Sign: may be negative. Negatives MUST be reported with explicit
  minus.
- Legal basis: RIRPF art. 110.1.a; AEAT Instrucciones.

**Casilla 04 — Importe del pago fraccionado**

- Type: EUR, computed.
- **General formula:** `04 = max(0, 0.20 × 03)`.
- **Ceuta/Melilla variant** (activities entitled to LIRPF art. 68.4
  deducción): `04 = max(0, 0.08 × 03)` — i.e., `0.20 × (1 − 0.60)`.
  Mixed cases apply 0.20 to the non-qualifying part and 0.08 to the
  qualifying part.
- **Voluntary upscale (RIRPF art. 110.4):** the taxpayer may choose
  a higher percentage. Once chosen for a quarter, not reversible.
- If `03 < 0`: `04 = 0` (never negative).
- Legal basis: RIRPF art. 110.1.a, 110.2, 110.4.

**Casilla 05 — Pagos fraccionados anteriores (Apartado I)**

- Type: EUR, computed.
- **Formula:**
  `05 = Σ(positive casilla 07 of prior quarters, same year)
       − Σ(casilla 16 of those same quarters)`.
  Negative 07 values of prior quarters are excluded from this sum
  (they propagate through casilla 15 instead).
- Legal basis: RIRPF art. 110.3.a. AEAT explicitly subtracts prior
  casilla 16 to prevent double-counting the vivienda-habitual
  deducción.

**Casilla 06 — Retenciones e ingresos a cuenta (Apartado I)**

- Type: EUR, user-entered. Sign ≥ 0. Scope: cumulative YTD.
- Covers retenciones on professional activity income and rental
  of urban real estate that is constitutiva de actividad económica
  (LIRPF arts. 95 y 101, RIRPF arts. 95 y 104).
- Legal basis: RIRPF art. 110.3.b.

**Casilla 07 — Resultado parcial Apartado I**

- Type: EUR, computed. Signed.
- **Formula:** `07 = 04 − 05 − 06`.
- May be negative; written with explicit minus.

### Apartado II — Actividades agrícolas, ganaderas, forestales y pesqueras

**Casilla 08 — Volumen de ingresos del trimestre (excluidas subvenciones de capital e indemnizaciones)**

- Type: EUR, user-entered. Sign ≥ 0.
- **Per-quarter (NOT YTD).** Unique to this apartado.
- Excludes subvenciones de capital y indemnizaciones; includes
  subvenciones corrientes.

**Casilla 09 — Importe del pago fraccionado**

- Type: EUR, computed.
- **General formula:** `09 = 0.02 × 08`.
- **Ceuta/Melilla variant:** `09 = 0.008 × 08` (i.e., 0.02 × 0.40).
- Voluntary upscale (RIRPF art. 110.4) available.
- Legal basis: RIRPF art. 110.1.b.

**Casilla 10 — Retenciones e ingresos a cuenta (Apartado II)**

- Type: EUR, user-entered. Sign ≥ 0. Scope: per-quarter (matches 08).

**Casilla 11 — Resultado parcial Apartado II**

- Type: EUR, computed. Signed.
- **Formula:** `11 = 09 − 10`.

### Apartado III — Total liquidación

**Casilla 12 — Suma de resultados parciales (nunca negativa)**

- Type: EUR, computed.
- **Formula:** `12 = max(0, 07 + 11)`. Algebraic sum first (so a
  negative 07 offsets a positive 11, and vice versa), then floored
  at zero. Algebraic negatives are preserved into casilla 12
  arithmetic but clipped at zero on output.
- Legal basis: AEAT Instrucciones ("De obtenerse una cantidad
  negativa, consigne el número cero (0)").

**Casilla 13 — Minoración por rendimientos netos del ejercicio anterior ≤ 12.000 €**

- Type: EUR, user-entered (conditional). Sign ≥ 0. Applied every
  quarter throughout the year.
- **Eligibility test (RIRPF art. 110.3.c):** based on
  *rendimiento neto previo a reducciones* in the last Modelo 100:
  estimación directa normal (Modelo 100 casilla 0224), estimación
  directa simplificada (1479), estimación objetiva (1553), atribución
  (1577). If no prior-year Modelo 100: eligible amount = 0, which
  lands in the ≤ 9.000 € tier ⇒ 100 € per quarter (new-autónomo
  first-year case).
- **Sliding scale (step function — no interpolation):**

  | rendimiento neto previous year (RN) | casilla 13 |
  |---|---|
  | 0 ≤ RN ≤ 9.000,00 € | 100 € |
  | 9.000,01 ≤ RN ≤ 10.000,00 € | 75 € |
  | 10.000,01 ≤ RN ≤ 11.000,00 € | 50 € |
  | 11.000,01 ≤ RN ≤ 12.000,00 € | 25 € |
  | RN > 12.000,00 € | 0 € |

- Legal-history caveat: LIRPF art. 80 bis ("deducción por obtención
  de rendimientos del trabajo o actividades económicas") was
  **repealed by Ley 26/2014** effective 2015-01-01. The *minoración*
  itself survived as RIRPF art. 110.3.c and is still in force for
  2024 and 2025.

**Casilla 14 — Neto tras minoración**

- Type: EUR, computed. Signed.
- **Formula (AEAT literal):** `14 = 12 − 13`, preserving sign.
- **Interpretive note:** AEAT Instrucciones say "de obtenerse una
  cantidad negativa, se hará constar con signo menos", which
  suggests algebraic unclipped. Most 3rd-party guides (Quipu,
  Infoautónomos, Cuéntica) floor it at 0 because 110.3.c is a
  *minoración* (not a refundable credit) — but the AEAT literal
  text prevails: the engine emits the algebraic value, and the
  downstream combined result (casilla 17 / 19) handles the "no
  refund" policy via the carry-forward mechanism.
- Decision for the engine: compute `14 = 12 − 13` signed; do not
  floor. Mark with audit note "AEAT allows signed negative per
  Instrucciones literal text".

**Casilla 15 — Arrastre de resultados negativos de trimestres anteriores (mismo ejercicio)**

- Type: EUR, user-entered (conditional). Sign ≥ 0 (sign is implicit
  minus when applied).
- **Eligibility:** only when `14 > 0`. Pool = `Σ |casilla 19 negativas
  de autoliquidaciones anteriores del mismo ejercicio|` minus
  Σ casilla 15 ya aplicadas en trimestres anteriores. Within-year
  only; negatives from 4T extinguish at ejercicio end (they roll
  into Modelo 100 as part of the annual rendimiento neto).
- **Cap:** `15 ≤ 14`. Any unused pool remainder survives for later
  quarters of the same year. Application order: at the next
  quarter with positive 14.
- Legal basis: RIRPF art. 110.3, último párrafo.

**Casilla 16 — Deducción por inversión en vivienda habitual (con financiación ajena)**

- Type: EUR, user-entered (conditional). Sign ≥ 0.
- **Formula:**
  `16 = min(0.02 × baseVivienda, 660.14, max(0, 14 − 15))`.
- **Base:**
  - Apartado I only ⇒ baseVivienda = casilla 03 (cumulative YTD).
  - Apartado II only ⇒ baseVivienda = casilla 08 (per-quarter,
    NOT YTD — matches the apartado's own base).
  - Both apartados operate ⇒ casilla 16 is **not applicable**
    (AEAT Instrucciones explicit bar).
- **Hard per-quarter cap:** 660,14 € (not cumulative).
- **Eligibility (all required):**
  1. Régimen transitorio de la DT 18ª LIRPF (acquisitions /
     rehabilitaciones before 2013-01-01 financed con financiación
     ajena).
  2. Rendimientos íntegros anuales previsibles < 33.007,20 € (for
     Ap. I, annualising Q1's cumulative ingresos).
  3. Volumen de ingresos anual previsible < 33.007,20 € (for Ap.
     II, annualising Q1's per-quarter volumen).
  4. The taxpayer has NOT communicated the deducción intent to
     the payer via Modelo 145.
  5. Adquisición or rehabilitación only (not construcción or
     ampliación) in this context.
- Legal basis: RIRPF art. 110.3.d; LIRPF DT 18ª.

**Casilla 17 — Diferencia (resultado antes de complementaria)**

- Type: EUR, computed. Signed.
- **Formula:** `17 = 14 − 15 − 16`.
- AEAT rule: if 17 is negative, 14 must also be negative and
  numerically equal (15 and 16 are both capped at non-negative).
- Feeds the cross-quarter arrastre pool through casilla 19.

**Casilla 18 — Resultado positivo a ingresar de autoliquidaciones anteriores del mismo trimestre (solo complementarias)**

- Type: EUR, user-entered. Sign ≥ 0.
- Only for autoliquidaciones complementarias replacing a prior
  filing for the same quarter. Captures the cantidad a ingresar
  of prior filings.

**Casilla 19 — Resultado final**

- Type: EUR, computed. Signed.
- **Formula:** `19 = 17 − 18`.
- If positive: resultado a ingresar.
- If negative: AEAT rule: "deberá reflejarse precedida del signo
  menos (–)", and 17 and 19 must equal numerically. Negative 19
  absolute value feeds the casilla-15 pool of subsequent quarters
  in the same ejercicio.

## Full casilla DAG (Modelo 130, 2024 and 2025)

```
USER INPUTS                    COMPUTED
------------                   ---------
01 (ingresos Ap.I) -------+
02 (gastos Ap.I) ---------+--> 03 (= 01 - 02, signed)
                                    |
                                    v
                               04 (= max(0, 0.20 * 03); 0.08 Ceuta/Melilla)
                                    |
(previous quarters' 07⁺, 16) --> 05 (= Σ07⁺ prev − Σ16 prev)
                                    |
06 (retenciones Ap.I) ----+         |
                          +-------> 07 (= 04 - 05 - 06, signed)
                                    |
08 (ingresos Ap.II) ------+         |
                          +-------> 09 (= 0.02 * 08; 0.008 Ceuta/Melilla)
                                    |
10 (retenciones Ap.II) ---+         |
                          +-------> 11 (= 09 - 10, signed)
                                    |
                          +-------> 12 (= max(0, 07 + 11))
                                    |
13 (minoración 110.3.c) --+         |
                          +-------> 14 (= 12 - 13, signed)
                                    |
(|19⁻| pool prev quarters) ----+    |
15 (arrastre, ≤14, user) ------+->
                                    |
16 (2% vivienda, user, capped)--+-> 17 (= 14 - 15 - 16, signed)
                                    |
18 (complementarias, user) -----+-> 19 (= 17 - 18, signed)
                                    |
                                    +-- neg: feeds casilla-15 pool later quarters
                                    +-- pos: resultado a ingresar
```

Cross-quarter feedback is unidirectional (19 → 15 of later quarters,
and 07⁺/16 → 05 of later quarters). Within a single quarter the DAG
is acyclic.

## Activity-combination logic

Modelo 130 is a single form with two disjoint apartados (I and II).
There is no separate "arrendamiento de inmuebles" apartado — rental
income only flows through 130 when the rental rises to the level of
"actividad económica" under LIRPF art. 27.2, and is declared inside
Apartado I.

- Per apartado, compute 07 and 11 independently. Both signed.
- Cross-apartado consolidation: `12 = max(0, 07 + 11)`. Algebraic
  sum first, then floor.
- Single-apartado taxpayers: the other apartado's fields are empty
  (= 0). A single negative 07 or 11 survives through 12 (as 0),
  then negative 14 / 17 / 19 opens the arrastre pool for next
  quarter.
- Casilla 13 applies once to the combined entity (12); eligibility
  uses the aggregate prior-year rendimiento neto from Modelo 100.
- Casilla 16 is mutually exclusive between apartados: if both
  operate, casilla 16 = 0 (not applicable).
- Casilla 15 pool is pool-based across the combined casilla 19,
  consumed first-available-quarter, capped by current casilla 14.

## Mid-year rule changes 2024 → 2025

The mechanical formulas in Modelo 130 are **identical between 2024
and 2025**. Verified by cross-referencing AEAT novedades pages
(2023 / 2024 / 2025), RD 1008/2023 (novedades IRPF 2024), and
consolidated-text reconstructions from Iberley and SuperContable:

| Rule | 2024 | 2025 | Change? |
|---|---|---|---|
| Apartado I rate (art. 110.1.a) | 20% | 20% | No |
| Apartado II rate (art. 110.1.b) | 2% | 2% | No |
| Ceuta/Melilla reduction (art. 110.2) | 60% | 60% | No |
| Casilla 13 scale (art. 110.3.c) | 100 / 75 / 50 / 25 € at thresholds 9k / 10k / 11k / 12k | Same | No |
| Vivienda habitual 2% & 660,14 € cap (art. 110.3.d) | Same | Same | No |
| Anualización threshold (33.007,20 €) | Same | Same | No |
| Arrastre de negativos intra-ejercicio | Same | Same | No |

**One genuine 2025 territorial delta — La Palma:** a 60% reduction
in the pago fraccionado rate (symmetric to Ceuta/Melilla's
mechanism) applies from 4T 2025 onward for taxpayers with residencia
habitual y efectiva en la isla de La Palma. Legal basis: **RDL
4/2024, de 26 de junio** (prórroga / ampliación of the La Palma
volcanic-eruption fiscal relief first introduced by RDL 20/2021),
reinforced by **RDL 13/2025, de 25 de noviembre** (BOE-A-2025-23911).
A transitional provision, not a change to RIRPF art. 110 itself. The
engine treats "La Palma 60% reduction" as a time-bounded
effective-rate override (effective 2025-10-01 through the periods
scheduled by the RDL's transitional regime).

Engine implication: the ruleset-versioning layer MUST support
territorial overrides as a parameterised dimension (`(modelo,
effective_from, effective_to, taxpayer_residency)`), not just a
date dimension.

Items flagged **UNVERIFIED**:

- La Palma arithmetic when combined with art. 110.2 Ceuta/Melilla
  (stack multiplicatively vs. mutually exclusive). The taxpayer
  population in that intersection is vanishingly small, but the
  engine must document the assumption when we implement the La
  Palma path.
- Casilla 14 floor behaviour: AEAT literal allows algebraic
  negative; 3rd-party guides floor. The engine adopts AEAT
  literal (see §casilla 14 decision).
- Modelo 100 casilla references (0224 / 1479 / 1553 / 1577) in
  the casilla-13 eligibility test. Modelo 100 renumbers boxes
  across years; coding the eligibility test must re-validate
  against the AEAT Manual Práctico IRPF of the corresponding
  year.

## Out of scope for Modelo 130 wave

Intentionally deferred to follow-up waves (documented in the plan
document's Wave 2+ section):

- **Wave 2: Modelo 303** — VAT quarterly autoliquidación. Uses the
  same engine but introduces new operators (ratios between IVA
  repercutido / soportado, prorrata, regularización anual).
- **Wave 3: Modelo 100** — annual personal income tax return.
  Extends into amortization tables, inventory valuation, property
  ownership, cross-reference against the amortizable asset registry
  vs. deductible expenses.
- **Wave 4 and beyond:** Modelo 390, 111, 115, 123, 347, 720, and
  full territorial / foral adaptations.

Each future wave is a separate vaultspec pipeline (research ⇒ ADR ⇒
plan ⇒ execute ⇒ review).

## Engine design — candidate architectures

The engine must codify AEAT Modelo calculation rules as
period-versioned rulesets, evaluate a DAG of casillas to produce
derived casillas, and support a **reverse audit** mode: given a
user-supplied casilla that the rules say is derivable, recompute
and flag discrepancies. Formulas come from (trusted-but-untested)
data authored by humans, so any user-controllable string that
reaches `eval` / `exec` / `compile` is a supply-chain vector.

Five candidate approaches:

1. **asteval** — AST-walking sandboxed interpreter, rich Python
   subset (loops, comprehensions, math/NumPy). Float-first;
   Decimal is second-class. Volunteers-run project explicitly
   declines to guarantee safety against malicious input. **Verdict:
   too powerful; float orientation clashes with the Decimal
   mandate; reject.**
2. **simpleeval** — single-file expression-only evaluator with
   whitelisted functions and DoS mitigations (`MAX_POWER` etc.).
   Operator coercion can silently demote `Decimal` to `float`.
   **Verdict: OK fallback but unnecessary attack surface once the
   primary DSL is in place; reject as primary.**
3. **sympy** — symbolic-math toolkit. Massive dependency,
   `sympify` has historical eval footguns, wrong problem shape.
   **Verdict: avoid for evaluation; revisit later as an offline
   property-test sidecar for forward/reverse algebraic equivalence.**
4. **Pure pydantic-graph DSL** — every formula is a pydantic v2
   model with `op: FormulaOp` enum, `operands: tuple[Operand, ...]`
   where `Operand = CasillaRef | Literal | ParamRef | Formula`
   (discriminated union). No parser, no string compilation. Prior
   art: JSON Logic ("we never eval()"), Google CEL, OpenFisca
   parameters. **Verdict: primary choice.**
5. **AST-whitelist** — custom `ast` visitor rejecting anything
   outside an operator whitelist. Odoo's `safe_eval` has had CVEs
   precisely because maintaining an AST whitelist across Python
   versions is hard. **Verdict: avoid as primary; consider a sealed
   `SafeExprFormula` operator for narrow cases if the pure DSL
   ever proves clumsy — gated behind an explicit allow-list.**

## Decimal arithmetic discipline

Rules adopted from Python's stdlib `decimal` documentation and
Spanish accounting convention (*redondeo comercial*):

- Every casilla value is `Decimal` at rest. No `float` enters the
  engine. YAML / JSON literals are loaded as strings and coerced
  via `Decimal(str_value)`.
- Intermediate computations carry 4 decimal places; published
  outputs quantise to 2 decimal places using `ROUND_HALF_UP`
  (NOT `ROUND_HALF_EVEN`, which is Python's default banker's
  rounding).
- Rate literals are stored as `Decimal("0.20")`, never `0.2`.
- Division must always `.quantize()` to a declared precision
  (never emit unbounded repeating decimals).
- Final rounding is a separate, explicit ledger node ("rounded
  from X to Y"), not an implicit side effect of multiplication
  or division.

## Period versioning — OpenFisca pattern

OpenFisca's date-keyed parameter tables are the canonical
open-source reference. Adopted verbatim:

- A `Ruleset` is a pydantic model carrying `effective_from: date`,
  `effective_to: date | None`, `modelo: ModeloCode`,
  `casillas: tuple[CasillaDefinition, ...]`,
  `formulas: tuple[FormulaDefinition, ...]`,
  `parameters: ParameterTable`.
- A `RulesetRegistry` indexes rulesets by modelo; `resolve(modelo,
  period)` returns the active one. If a period spans a rule
  change, the registry raises `AmbiguousPeriodError` and the
  caller splits.
- Rate parameters (e.g., IRPF 0.20) live in a date-keyed
  `ParameterTable`, not inline in formulas. Formulas reference
  them by `ParamRef("irpf.trimestral_rate")`.
- Territorial overrides (Ceuta/Melilla, La Palma) are a
  parameterised dimension alongside the date axis.

## DAG evaluation — `graphlib`

Python's stdlib `graphlib.TopologicalSorter` is sufficient:

- `ts.add(node, *predecessors)` builds the graph.
- `ts.prepare()` raises `CycleError` (subclass of `ValueError`)
  if any cycle is detected; the engine wraps this into
  `aeat.core.errors.FormulaCycleError` carrying the cycle and the
  offending ruleset id.
- `ts.static_order()` returns the evaluation order as an iterator.
- No `networkx` dependency — Modelo-scale DAGs are at most low
  hundreds of nodes; `graphlib` is 10 lines of stdlib.

## Forward and reverse evaluation (double-accounting robustness)

The engine exposes two modes over the same ruleset:

- **Forward (`derive`)** — given inputs, topologically sort derived
  casillas, compute each, emit a `ComputationLedger` with one
  `LedgerEntry` per node (casilla, value, operator, operand values,
  formula id, ruleset version).
- **Reverse (`audit_against`)** — given a user-supplied value for
  a derived casilla, recompute and compare. If the delta exceeds
  the tolerance (`Decimal("0.01")`, one cent), emit a `Discrepancy`
  with casilla, user value, computed value, delta, formula id,
  and contributing casillas. The caller either accepts the
  computed value, or overrides with a documented reason stored on
  the discrepancy record.

Both modes share the same ledger format. The ledger is the
auditability substrate — every emitted value is traceable to
either (a) an input the user supplied with a source reference, or
(b) a formula node with its operands.

## Subpackage layout

Recommended layout for `src/aeat/domain/formulas/`:

```
src/aeat/domain/formulas/
  __init__.py        # public API re-exports
  _codes.py          # FormulaOp StrEnum
  _casilla.py        # CasillaDefinition, CasillaRef
  _formula.py        # Formula pydantic model (discriminated union)
  _ruleset.py        # Ruleset (effective_from/to, modelo, ...)
  _registry.py       # RulesetRegistry.resolve(modelo, period)
  _engine.py         # Engine.derive / Engine.audit_against
  _ledger.py         # ComputationLedger, LedgerEntry, Discrepancy
  _errors.py         # FormulaCycleError, CasillaNotDefinedError,
                     # AmbiguousPeriodError, FormulaValidationError
  _rulesets/         # concrete rulesets
    __init__.py
    modelo_130_2024.py
    modelo_130_2025.py
  _cli.py            # aeat formulas list / show / compute
  test_*.py          # colocated @pytest.mark.unit tests
```

All symbols are re-exported from `aeat.domain.formulas` (public-API
discipline mandate).

## Sources cited

Primary (AEAT / BOE — authoritative):

- [AEAT — Instrucciones Modelo 130](https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-130-irpf______esionales-estimacion-directa-fraccionado_/instrucciones.html)
- [AEAT — Importe de los pagos fraccionados](https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/pagos-fraccionados/importe-pagos-fraccionados.html)
- [BOE — RD 439/2007 consolidado (Reglamento IRPF)](https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820)
- [AEAT-hosted Ley 35/2006 (IRPF-2024 Normativa)](https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2024/Normativa-IRPF24/Ley-35-2006.pdf)
- [AEAT — Novedades IRPF 2023 (RD 1008/2023)](https://sede.agenciatributaria.gob.es/Sede/irpf/novedades-impuesto/novedades-normativa-2023/principales-novedades-real-decreto-1008-diciembre.html)
- [BOE — RDL 13/2025 (La Palma)](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-23911)

Secondary 3rd-party (corroboration only):

- [Iberley — Artículo 110 RD 439/2007](https://www.iberley.es/legislacion/articulo-110-reglamento-impuesto-sobre-renta-personas-fisicas-irpf)
- [SuperContable — Artículo 110 RD 439/2007](https://www.supercontable.com/informacion/impuesto_renta_IRPF/Articulo_110_Real_Decreto_439-2007-_de_30_de_marzo-_.html)
- [Infoautónomos — Casilla 13 Modelo 130](https://www.infoautonomos.com/blog/casilla-13-del-modelo-130-irpf/)
- [Ayudatpymes — Casilla 13 Modelo 130](https://ayudatpymes.com/gestron/casilla-13-modelo-130/)
- [Quipu — Casilla 13 Modelo 130](https://getquipu.com/blog/casilla-13-modelo-130-irpf/)
- [Declarando — Modelo 130 guía](https://declarando.es/modelo-130)
- [Cuéntica — Modelo 130](https://cuentica.com/asesoria/que-es-el-modelo-130-y-como-se-cumplimenta/)
- [Genealia — Modelo 130 2025](https://www.genealia.es/modelo-130-pago-fraccionado-del-irpf/)
- [TeamSystem — Novedades IRPF 2025](https://teamsystem.es/magazine/novedades-declaracion-irpf-2025/)
- [Glasof — Renta 2025 novedades](https://www.glasof.es/blog/renta-2025-novedades-clave-que-debes-conocer)
- [Anfix — Deducción 400 € Modelo 130](https://www.anfix.com/blog/ha-desaparecido-la-deduccion-de-los-400-euros-del-modelo-130)

Engine design:

- [asteval docs](https://lmfit.github.io/asteval/)
- [simpleeval README](https://github.com/danthedeckie/simpleeval)
- [Python stdlib `graphlib.TopologicalSorter`](https://docs.python.org/3/library/graphlib.html)
- [Python stdlib `decimal`](https://docs.python.org/3/library/decimal.html)
- [OpenFisca periods](https://openfisca.org/doc/coding-the-legislation/35_periods.html)
- [OpenFisca legislation parameters (date-keyed YAML)](https://openfisca.org/doc/coding-the-legislation/legislation_parameters.html)
- [JSON Logic manifesto](https://jsonlogic.com/)
