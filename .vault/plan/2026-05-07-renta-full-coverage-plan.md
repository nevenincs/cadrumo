---
tags:
  - '#plan'
  - '#renta-full-coverage'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - "[[2026-05-07-renta-scope-audit-audit]]"
  - "[[2026-05-06-renta-cuota-chain-rollout-plan]]"
  - "[[2026-05-03-calculation-truth-registry-pending-adr]]"
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
  - "[[2026-04-21-modelo-100-renta-research]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-research]]"
  - "[[2026-05-03-calculation-truth-inventory-research]]"
  - "[[2026-05-04-calculation-authority-evidence-tiering-research]]"
---



# `renta-full-coverage` plan

The singular typed-out plan that lists every exec step required to take
Modelo 100 from 2.6 percent casilla coverage to a complete Renta filing
surface. Every commit that touches the Renta calculation surface must
reference a phase number from this plan in its commit message, so
progress is attributable, ordered, and audit-traceable.

The plan flows from the renta scope audit (2026-05-07). The audit's
brutal numbers are the starting line; this plan's phases are the route
to honest coverage. Every phase has explicit substrate prerequisites,
acceptance criteria expressed as audit-metric movements (casilla
coverage percent, archetype coverage count, mini-model coverage
percent, test honesty distribution), and pydantic-backed typed-substrate
deliverables.

## Foundational principles

- **No fake coverage.** Tests with all-zero inputs and all-zero
  expected outputs do not count toward coverage. The hygiene guard at
  `test_renta_synthetic_scenarios_do_not_pass_with_pure_zero_inputs_to_zero_outputs`
  enforces this. Every phase that ships behaviour tests must include
  at least one non-trivial numeric assertion derived independently of
  the formula being tested.
- **Typed-substrate surfaces only.** Every Renta domain field that
  classifies a substrate axis (income type, autonomous community,
  estimación directa modality, ganancias modality) consumes a pydantic
  v2 closed-membership enum. No free-form `str | None` fields for
  substrate axes. Pattern mirrors `aeat.domain.vat` (`VATCategory`,
  `EUMemberState`, `VATRateKind`).
- **Pydantic-backed legal bindings.** Every formula's `legal_refs` and
  `source_citations` resolve through the typed binding surface
  introduced by the IVA rollout (commit `688609e5`). Article id, BOE
  permalink, evidence_tier, and corpus byte-range are typed fields,
  not strings parsed at runtime.
- **Honest substrate-first ordering.** Mini-model formula slices land
  AFTER the substrate that grounds them (typed enums, catalogued
  legal articles, registered parameters). A mini-model slice that
  ships before its substrate is a coverage lie.
- **Audit-driven progression.** Every slice that lands triggers an
  audit refresh (`scripts/audit_renta_scope.py`) and a sync of the
  rolling gaps inventory. The audit metrics are the contract; they
  must monotonically improve.
- **Centralized backends, zero duplication.** The grounding
  framework already exists. Every slice MUST code-dip the relevant
  module before authoring. New helpers, parity wrappers, or local
  shims are forbidden when a centralized backend covers the need.
  The mandatory backends are listed under "Grounding framework
  backends" below; any new pydantic model subclasses
  `RegistryModel`, `RentaWebOpenModel`, or `WorkbookParityModel`
  (all strict-frozen, extra-forbid) — never `BaseModel` directly.

## Grounding framework backends

The repository already carries the infrastructure for grounded
calculation verification. Slices that ignore these backends and
re-implement them are rejected at review time. The backends:

- **`_renta_web_open_oracle.py`** — `RentaWebOpenOracle` is the
  PRIMARY grounding oracle for Modelo 100. AEAT publishes no
  executable workbook for Renta; their canonical calculator is the
  server-side Renta WEB Open simulator. The oracle wraps that
  surface through `RentaWebOpenDriver` (Protocol),
  `RentaWebOpenReplayDriver` (deterministic replay from captured
  payloads), `RentaWebOpenLivePayload` /
  `RentaWebOpenObservation` / `RentaWebOpenSyntheticProfile`
  (pydantic strict-frozen records). Every Modelo 100 calculation
  scenario MUST carry a replay payload that pins the oracle's
  expected outputs. Live capture goes through the Playwright
  driver in `src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py`
  (`RentaWebOpenSedeDriver` + `collect_renta_web_open_observation`).

- **`_workbook_parity.py`** — workbook discovery, scan, parity
  comparison, and LibreOffice-headless / Excel-COM execution for
  AEAT-published executable workbooks. Modelo 100 has no executable
  workbook (only `record_design_layout` xlsx for 2015-2019 and the
  XSD dictionary for 2025); therefore Modelo 100 uses workbook
  parity ONLY as layout-authority evidence, not calculation oracle.
  Other modelos (130, 131, 303) have executable formula workbooks
  and use this backend as the primary oracle.

- **`_formula_runtime.py`** — `calculate_registry_snapshot` is the
  registry's calculation engine. Every formula's `op` value
  (`add`, `subtract`, `sum`, `multiply`, `divide`, `percent`,
  `min`, `max`, `clamp`, `negate`, `if_then_else`,
  `lookup_parameter`, `previous_period_value`, `previous_period_sum`,
  `cross_model_sum`, etc.) routes through this engine. New ops are
  added by extending the runtime here, never by per-modelo
  dispatch.

- **`_scenarios.py`** — `RegistryCalculationScenario` +
  `run_registry_calculation_scenario` +
  `assert_registry_scenario_matches`. Every formula scenario test
  uses these, never bespoke runners.

- **`_schema.py`** — `RegistryModel` (strict, frozen, extra-forbid)
  is the base for every registry record. Schema fields like
  `typed_enum: str | None` (added in commit `d21f9dd4`) are added
  here once and used everywhere; per-modelo extensions are
  forbidden.

- **`scripts/audit_renta_scope.py`** — the rolling audit driver.
  Every slice ends with a refresh and a metric movement. New audit
  layers extend this script; per-feature mini-audits are forbidden.

The plan's slices reference these backends by name, not by
re-implementation. A slice that proposes a new oracle or workbook
runner must first justify (in its exec record) why the central
backends do not fit, and the justification must survive review.

## Phase dependency graph

S1 (typed enums) and S2 (legal articles) feed all downstream phases.
S3 (cross-modelo relations) and S4 (escala parameters) feed the cuota
chain and the autonomic deductions chain. Mini-model phases (MM-1
through MM-8) consume the substrate. Scenario phases (Sc-A2 through
Sc-E1) consume both the substrate and the mini-models. Hardening
phases (H1 through H5) run in parallel and gate quality.

## Substrate phases (S1-S4)

### Phase S1 — Renta typed enums

**Status: DELIVERED 2026-05-07 (commit `1113197e`)**

`RentaIncomeType` (11 members), `RentaCCAA` (19 members),
`EstimacionDirectaModalidad` (2 members) registered at
`src/aeat/domain/renta/_substrate.py`. 8 membership + round-trip
tests pass. Mirrors the IVA closed-membership pattern.

Pending follow-up: bridge `renta-2025-profile-tax-residence-ccaa`
and `renta-2025-modelo-100-estimacion-directa-es-normal` bindings to
consume the typed enums (covered under H4 typed-binding rollout).

### Phase S2 — Legal article catalogue closure

**Status: PARTIAL DELIVERED 2026-05-07 (commit `93bb53f4`)**

Already catalogued at audit baseline: arts 17, 18, 19, 20, 22, 23,
24, 25, 26, 27, 28, 30, 31, 32, 49, 50, 56, 62, 63, 66, 67, 68, 73,
74, 75, 77, 85, 99 (28 articles). Added in S2 partial: arts 33, 34,
37, 82, 83. 33 articles now catalogued.

Remaining (deferred to mini-model substrate as each is needed):
- art-35, 36 — transmisión onerosa / lucrativa subcasos (needed by
  MM-4 deeper)
- art-68 sub-points — deducciones generales (needed by MM-2)
- art-81-bis — deducción por maternidad (needed by C1/C2)
- art-90, 91 — atribución de rentas, transparencia internacional
  (needed by MM-6)

### Phase S3 — Cross-modelo relations + dep_classifications + constructs backport

**Status: PENDING (Task #42)**

Currently the 9 cross-modelo relations + 8 previous_filing target
bindings + 9 dep_classifications + 8 constructs exist only in 2025.
Backport to 2020-2024 with year-scoped clones. Substantial substrate
clone (~250 lines per year × 5 years).

Substrate prerequisite: none.
Acceptance: every supported revision (2020-2025) carries the 9
relations + 8 target_bindings + 9 dep_classifications + 8 constructs;
audit Layer 3 retenciones_pagos_a_cuenta coverage moves above 11.1
percent.

### Phase S4 — Escala progresiva parameters per ejercicio

**Status: PENDING (Task #44)**

Encode each ejercicio's IRPF estatal escala (LIRPF art. 63) and
autonomic default escala (LIRPF art. 74) bracket values as registry
parameters with date_axis filing_period. Year-specific deltas per
CCAA live in MM-1 sub-slices.

Substrate prerequisite: S2 art-63 + art-74 (already catalogued).
Acceptance: replace the manual 0528, 0529, 0530, 0531 inputs in
synthetic scenarios with formula-derived values.

## Mini-model formula phases (MM-1 to MM-8)

### Phase MM-1 — Anexo B autonomic deductions per CCAA

**Status: PENDING (482 casillas, 0 percent coverage)**

The largest single uncovered surface. Recommended decomposition: one
sub-slice per CCAA (17 + 2 = 19 sub-slices). Each sub-slice ships a
per-CCAA construct grounded in that CCAA's Decreto Legislativo, formula
or binding declarations for the ~30 CCAA-specific casillas, and per-
CCAA legal article additions if needed.

Substrate prerequisite: S1 RentaCCAA (delivered), S2 art-74, plus
per-CCAA legal article additions per sub-slice.
Acceptance: per-CCAA sub-slice landed when at least 50 percent of
that CCAA's casillas are computed or bound; audit Layer 3
anexo_b_autonomicas coverage moves from 0 toward 100 per sub-slice.

### Phase MM-2 — Anexo A general deductions

**Status: PENDING (173 casillas, 0 percent coverage)**

LIRPF art-68 sub-points: vivienda habitual transitorio, inversión
empresas nueva creación, donativos, cultural, inversión empresarial,
alquiler vivienda transitorio, eficiencia energética. 6 deduction-
construct sub-slices.

Substrate prerequisite: S2 art-68 sub-points (deferred S2 follow-up).
Acceptance: 6 sub-slices land; audit Layer 3 anexo_a_estatal coverage
moves above 50 percent.

### Phase MM-3 — Capital inmobiliario per-property breakdown

**Status: PENDING (154 casillas, 2.6 percent coverage)**

The Python rental tier resolver in `src/aeat/domain/rental/`
implements LIRPF art. 23 thresholds. Wire those thresholds into
registry parameters (Task #50) and migrate the rental aggregation
chain into per-property registry formulas.

Substrate prerequisite: S2 art-22, 23, 24 (delivered), plus a
registry-backed rental tier resolver in `_tier_resolver.py` that
loads thresholds from registry parameters.
Acceptance: per-property real-estate aggregation casillas computed;
rental tier thresholds live as registry parameters.

### Phase MM-4 — Ganancias y pérdidas per-transaction breakdown

**Status: PARTIALLY UNBLOCKED (saldo formulas 0420, 0421, 0424, 0425
delivered for 2020-2025; per-transaction inputs still manual)**

Saldo aggregation formulas (max(positive - negative, 0)) landed in
commits `fdd14f31` (2020-2024) and `fc0403dd` (2025). Next layer:
formulas that aggregate per-transaction inputs (sale of fund / sale
of property / sale of rights / criptomonedas) into 0418, 0419, 0422,
0423.

Substrate prerequisite: S2 art-33, 34, 37 (DELIVERED), plus art-35,
36 for transmisiones onerosas / lucrativas detalladas (deferred).
Acceptance: at least one per-transaction breakdown formula per
ganancia type; audit Layer 3
ganancias_capital_mobiliario_ahorro coverage moves above 5 percent.

### Phase MM-5 — Estimación objetiva (modules)

**Status: PENDING (113 casillas, 0 percent coverage)**

Modules-based business income for small autónomos and agricultural
activities. Year-scoped parameter table for module rates per
actividad.

Substrate prerequisite: S2 art-31 (DELIVERED), plus per-year
estimación-objetiva ordenes catalogued.
Acceptance: per-actividad rendimiento neto formulas computed for at
least one año; audit Layer 3 actividades_economicas_objetiva coverage
moves above 30 percent.

### Phase MM-6 — Atribución de rentas + transparencia

**Status: PENDING (312 casillas, 0 percent coverage)**

Rentas atribuidas por entidades en régimen de atribución (sociedades
civiles, comunidades de bienes), art. 85 imputación de rentas
inmobiliarias, transparencia fiscal internacional (art. 91-95).
Wires Modelo 184 + 232 cross-modelo relations into Renta.

Substrate prerequisite: S2 art-85 (DELIVERED), art-90, 91 (deferred);
S3 cross-modelo relations backport.
Acceptance: at least one atribución formula per source-modelo type;
audit Layer 3 regimenes_atribucion coverage moves above 25 percent.

### Phase MM-7 — Anexo C Canarias (RIC, ZEC)

**Status: PENDING (179 casillas, 0 percent coverage)**

Régimen Económico-Fiscal de Canarias: Reserva para Inversiones (Ley
19/1994 art. 27), Zona Especial Canaria (Ley 19/1994 art. 42-49),
ventas de bienes corporales producidos en Canarias.

Substrate prerequisite: catalogue Ley 19/1994 articles (currently
absent from `registry/aeat/legal/`).
Acceptance: at least RIC + ZEC + ventas-bienes-canarias deduction
formulas; audit Layer 3 anexo_c_canarias coverage moves above 50
percent.

### Phase MM-8 — Regímenes especiales (UTE, AIE, buques navieras Canarias)

**Status: PENDING (85 casillas, 0 percent coverage)**

Uniones Temporales de Empresas (LIS art. 45), Agrupaciones de Interés
Económico (LIS art. 43-44), régimen especial de buques y empresas
navieras en Canarias.

Substrate prerequisite: catalogue LIS art-43, 44, 45.
Acceptance: at least one régimen especial formula; audit Layer 3
regimenes_especiales coverage moves above 30 percent.

## Scenario coverage phases (Sc-A2 to Sc-E1)

Each scenario phase ships a synthetic-profile test that exercises the
end-to-end chain with non-trivial inputs and asserts specific non-
trivial outputs.

### Phase Sc-A2 — Employee + capital mobiliario savings interest

Substrate prerequisite: MM-4 saldo aggregator formulas (delivered).
Acceptance: scenario test with non-trivial 0429 + 0424 inputs; audit
Layer 7 A2 archetype goes from false-positive to genuine coverage.

### Phase Sc-A3 — Employee + property rental income

Substrate prerequisite: MM-3 capital inmobiliario per-property
formulas.
Acceptance: scenario test with at least one rental property; audit
Layer 7 A3 archetype covered.

### Phase Sc-B1 — Autónomo direct estimation normal mode

Substrate prerequisite: trabajo + estimación directa formulas
(delivered); modal binding (delivered); per-row payroll / gastos
inputs.
Acceptance: scenario test with `EstimacionDirectaModalidad.NORMAL`;
chain produces 0224 = 0180 - 0220 and propagates through the income
side to 0432.

### Phase Sc-B2 — Autónomo direct estimation simplified

Substrate prerequisite: same as B1 plus difficult-justification
parameters (delivered).
Acceptance: scenario test with
`EstimacionDirectaModalidad.SIMPLIFICADA`; chain correctly applies
the 5 percent rate / 2,000 EUR cap on difficult-justification
expenses.

### Phase Sc-B3 — Autónomo objective estimation (modules)

Substrate prerequisite: MM-5.
Acceptance: scenario test with module inputs; chain computes
rendimiento neto from modules.

### Phase Sc-C1 — Family unit joint declaration

Substrate prerequisite: S2 art-82, 83 (delivered); MM-2 family-
related deductions; tributación-conjunta reducción formula.
Acceptance: scenario test with declaration_type joint; chain applies
3,400 EUR reducción tributación conjunta to base liquidable general.

### Phase Sc-C2 — Family with descendants / ascendants / discapacidad

Substrate prerequisite: family-row profile bindings (in flight).
Acceptance: scenario test with descendant / ascendant / discapacidad
profile rows; 0513-0518 mínimos populated from row aggregation.

### Phase Sc-D1 — Capital gains transactions

Substrate prerequisite: MM-4 per-transaction breakdown.
Acceptance: scenario with multiple ganancias / pérdidas events; cuota
chain absorbs the saldo positive into base imponible del ahorro.

### Phase Sc-E1 — CCAA-specific autonomic deduction

Substrate prerequisite: MM-1 per-CCAA sub-slices.
Acceptance: scenario per CCAA with at least one autonomic deduction
applied; 0564 suma de deducciones autonómicas correctly populated.

## Hardening phases (H1-H5)

### Phase H1 — Per-formula corpus byte-range validation (Layer 2)

For every formula's `source_citations[].required_text`, validate
that the phrase actually appears in the cited corpus byte-range.
Catches stale citations and fabricated grounding immediately. Run
as pytest test in `test_renta_legal_grounding_audit.py`.

### Phase H2 — Cross-modelo relation closed-loop validation (Layer 5)

For each Modelo 100 cross-modelo relation, verify the source
modelo's revision actually exposes the declared `source_output`,
the period_alignment shape matches the source modelo's period
structure, and the inverse declaration on the source modelo side
exists.

### Phase H3 — External-surface registration audit (Layer 6)

For each Renta external surface (Renta WEB Open, Renta WEB
authenticated, borrador / datos fiscales, justificante), verify
live cross-reference declared, remote-state guard policy in place,
adapter registered, test coverage.

### Phase H4 — Typed-binding rollout

Bridge every Renta `str | None` substrate axis to its corresponding
typed enum. Mirrors the IVA `c2fc4e24` Invoice.iva_category typed-
promotion pattern.

Substrate prerequisite: S1 (delivered).
Acceptance: zero free-form `str | None` substrate-axis fields in
the Renta domain; the audit driver gains a Layer 9 (typed-binding
inventory) to enforce.

### Phase H6 — Renta WEB Open oracle linkage (mandatory grounding)

**Status: PENDING (Tasks #79, #80, #81, #82, #83, #84)**

Every Modelo 100 calculation scenario in `test_renta_chain_behaviour`
and `test_renta_2025_synthetic_profile` MUST carry a replay payload
captured from AEAT's Renta WEB Open simulator. The payload is fed
through `RentaWebOpenReplayDriver` to `RentaWebOpenOracle.verify_payload`,
and the oracle's parity verdict (`match` / `mismatch` / `unverifiable`)
is asserted alongside the existing
`assert_registry_scenario_matches`.

The capture pass uses `RentaWebOpenSedeDriver` (Playwright) against
the live AEAT endpoint. Live captures are gated by
`AEAT_LIVE_TESTS_ENABLED=1` and log Playwright traces for evidence.
Subsequent runs replay only.

A permanent hygiene gate
(`test_every_renta_formula_has_oracle_replay_coverage`) enforces:
for every formula whose target casilla is NOT envelope-bound or
profile-bound, at least one scenario's replay payload must observe
that target. The gate cannot be skipped or muted.

Substrate prerequisite: existing `_renta_web_open_oracle.py` +
`_renta_web_open.py` (DELIVERED).
Acceptance: every chain-behaviour and synthetic-profile scenario
ships a replay payload + oracle assertion; hygiene gate runs as
unit test in `test_schema_hygiene.py`; zero formula targets escape
oracle-grounded coverage.

### Phase H5 — Test honesty enforcement (extended)

**Status: PARTIAL (vacuous-pattern guard delivered)**

Existing guard at
`test_renta_synthetic_scenarios_do_not_pass_with_pure_zero_inputs_to_zero_outputs`
catches the all-zero pattern. Extended H5 adds: guard against
`assert actual == formula(inputs)` patterns where the test re-
implements the formula; guard against scenarios that cite non-
existent operand_refs; guard against tests marked skip / xfail
without an explicit registry-backed reason; audit Layer 8
monotonic-improvement check.

## Continuous coordination

After every phase commit, the autonomous loop runs:

1. Pytest: `uv run --no-sync pytest src/aeat/domain/renta/
   src/aeat/domain/calculations/registry/` to confirm regression-free.
2. Audit refresh: `uv run --no-sync python scripts/audit_renta_scope.py`.
3. Update the corresponding phase entry from PENDING to DELIVERED
   with the commit hash and the audit-metric movement that the
   phase produced.
4. Commit (hooks bypassed under explicit user direction).
5. Re-open the audit refresh repetitive task for the next cycle.

Phase numbering is stable: subsequent autonomous loop sessions
reference phases by number. New slices that emerge from substrate
discovery are appended; numbering is never recycled.

The plan is complete when:
- All 4 substrate phases (S1, S2, S3, S4) are delivered.
- All 8 mini-model phases (MM-1 through MM-8) are delivered.
- All 9 scenario phases (Sc-A2, A3, B1, B2, B3, C1, C2, D1, E1) are
  delivered.
- All 6 hardening phases (H1, H2, H3, H4, H5, H6) are delivered.
- 100 percent of chain-arithmetic casillas (every casilla whose
  AEAT label or BOE definition prescribes an explicit formula over
  other casillas) are computed by registry formulas. Pure manual-
  input casillas (taxpayer-supplied values such as property
  appraisals or donation amounts) remain manual by AEAT design and
  are excluded from the 100 percent target.
- The audit's archetype coverage reaches 10 of 10.
- Every formula has at least one Renta WEB Open replay payload
  scenario asserting parity (Phase H6 hygiene gate).
- Audit Layer 8 reports zero vacuous patterns and zero structural-
  only synthetic-profile test files.

27 phases total. Substrate phases unblock mini-model phases; mini-
model phases unblock scenario phases; hardening phases run in
parallel and cover the audit metrics that scope phases do not
directly move. Every implementation phase pairs with a code-review
task that verifies pydantic enrollment, backend reuse, and dict /
oracle grounding before the phase is marked DELIVERED.
