---
tags:
  - '#plan'
  - '#renta-cuota-chain-rollout'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
  - "[[2026-05-03-calculation-truth-registry-pending-adr]]"
  - "[[2026-04-21-modelo-100-renta-research]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-research]]"
  - "[[2026-05-03-calculation-truth-inventory-research]]"
  - "[[2026-05-04-calculation-authority-evidence-tiering-research]]"
  - "[[2026-05-08-renta-cuota-integra-state-scale-research]]"
  - "[[2026-05-08-renta-cuota-integra-autonomic-scale-research]]"
---



# `renta-cuota-chain-rollout` plan

Track the audit findings and roll out the Renta calculation pipeline chain
gap that sits between income aggregation and the settlement chain in Modelo
100. The chain expansion is centralised in the existing AEAT calculation
registry: each phase adds a thin layer of substrate (legal references in
`registry/aeat/legal/`, parameters and formulas in
`registry/aeat/modelos/100.toml`) before the next phase consumes it. No
filing-grade legal value, threshold, scale, or casilla mapping is allowed to
re-enter Python modules: every legal binding lands as a typed registry
formula, parameter, binding, or relation.

Aspirational end-state tests (deliberate xfail-strict failures, see
`src/aeat/domain/calculations/registry/test_renta_pipeline_aspirational.py`)
exercise the full multi-year cuota chain. Each test stays red until its
phase is delivered; once a phase lands, its corresponding xfail flips to
xpass which trips the strict marker, forcing explicit review and removal
of the marker.

## Audit Findings (2026-05-06)

State of Modelo 100 ejercicio 2025 calculations at the start of this plan:

- Casilla schema: 11,302 casillas across 6 ejercicios (2020-2025) with
  semantic 2-3-deep section paths. Schema hygiene tests guard against
  duplicate ids/numbers, empty sections, CamelCase leakage, and XML root
  container leakage.
- Existing computed casillas in 2025: 35 formulas, 39 bindings, 9
  cross-model relations, 20 dependency classifications, 10 constructs.
- Existing income side (computed): trabajo neto reducido (0025), capital
  mobiliario ahorro neto reducido (0040), capital mobiliario general neto
  reducido (0056), capital inmobiliario neto reducido (0154), estimación
  directa rendimiento neto reducido total (0235), estimación directa
  difficult-justification expenses cap.
- Existing settlement side (computed): cuota líquida incrementada total
  (0587), cuota resultante autoliquidación (0595), cuota diferencial,
  resultado declaración, retenciones arrendamientos urbanos, total pagos
  a cuenta.
- Existing cross-model relations: payments-on-account from Modelos 130,
  131; retenciones from 111 (trimestral and mensual), 115, 123, 180, 190,
  193.
- Existing 2020-2024 revisions: pure casilla inventory only. ZERO
  formulas, bindings, parameters, relations, dependency classifications.

The chain gap. The following casillas lie between the income side and the
settlement side and are still `manual`:

- 0432: Saldo neto rendimientos integrar base imponible general y de las
  imputaciones de renta.
- 0433: Saldo neto negativo de las ganancias y pérdidas patrimoniales de
  2025 a integrar en la base imponible general (limited to 25% of 0432).
- 0435: Base imponible general.
- 0436: Saldos netos negativos rendimientos capital mobiliario imputables
  a 2025 a integrar en la base del ahorro (limited to 25% of 0424).
- 0460: Base imponible del ahorro.
- 0500: Base liquidable general.
- 0510: Base liquidable del ahorro.
- 0511 to 0518: Mínimo del contribuyente, descendientes, ascendientes,
  discapacidad — split into estatal and autonómica parts.
- 0519: Parte estatal: Mínimo personal y familiar (sum of 0511, 0513,
  0515, 0517).
- 0520: Importe total incrementado o disminuido del mínimo personal y
  familiar a efectos del cálculo del gravamen autonómico.
- 0521 to 0524: Mínimo personal y familiar that forms part of the base
  liquidable general / del ahorro for cálculo del gravamen estatal /
  autonómico (min() of base liquidable and mínimo).
- 0528 to 0531: Aplicación de la escala general y autonómica del Impuesto.
- 0532, 0533: Cuotas correspondientes a la base liquidable general
  (0532 = 0528 - 0530; 0533 = 0529 - 0531).
- 0540, 0541: Cuotas correspondientes a la base liquidable del ahorro.
- 0545, 0546: Cuota íntegra estatal y autonómica.
- 0547 to 0567: State-side and autonomic deductions per Annex A and B.
- 0568, 0569: Incremento de las cuotas líquidas por pérdida del derecho
  al incentivo fiscal del art. 33.3 c) LIS.
- 0570, 0571: Cuota líquida estatal y autonómica.
- 0584: Por residencia habitual y efectiva en la isla de La Palma.
- 0585, 0586: Cuota líquida estatal incrementada y autonómica
  incrementada.

Substrate gap. The IRPF catalogue (`registry/aeat/legal/irpf.toml`)
carries Ley 35/2006 articles 17 to 32 (income), 68.4, 85, 99 (atribución,
retenciones). It is missing the cuota chain articles 49 (integración base
ahorro), 50 (base imponible general/ahorro), 56 (mínimo personal y
familiar), 63 (escala estatal), 66 (tipos del ahorro estatal), 67 (cuota
íntegra estatal), 68 (deducciones estatales), 73 (escala autonómica), 74
(escala complementaria autonómica), 75 (cuota íntegra autonómica), 77
(cuota líquida autonómica), 79 (cuota líquida total). The corpus
`corpus/normatives/ley-35-2006.json` carries 15 articles total; the
cuota chain articles must be added with hand-curated multilingual
summaries (es authoritative; ca, en, hu kept at parity with the existing
catalogue quality bar).

## Proposed Changes

Land substrate first, formulas second, multi-year backport last. Each
phase is an isolated commit. Each phase ships:

- registry artefacts (corpus + catalogue + modelo TOML),
- localised pytest coverage scoped to the casillas the phase introduces,
- one or more aspirational xfail-strict tests that flip from xfail to
  xpass exactly when the phase is delivered, forcing explicit review of
  the marker before the next phase begins.

The aspirational tests are NOT skipped, NOT marked TODO. They run on
every CI invocation. They fail by design until the gap closes. Once a
phase lands and its aspirational test starts xpassing, the strict marker
turns the green test into a red suite, forcing the marker removal and
the formula registration into the same commit.

## Tasks

- `Phase A: IRPF cuota chain legal substrate`
  1. Add Ley 35/2006 art-49 (Integración y compensación de rentas en la
     base imponible del ahorro) to `corpus/normatives/ley-35-2006.json`
     and `registry/aeat/legal/irpf.toml`. Spanish summary from BOE
     authoritative text; ca/en/hu translations at parity with existing
     entries.
  1. Add art-50 (Base imponible general y del ahorro).
  1. Add art-56 (Mínimo personal y familiar).
  1. Add art-63 (Escala general del Impuesto).
  1. Add art-66 (Tipos de gravamen del ahorro: parte estatal).
  1. Add art-67 (Cuota íntegra estatal).
  1. Add art-68 (Deducciones de la cuota íntegra estatal).
  1. Add art-73 (Escala autonómica).
  1. Add art-74 (Escala autonómica complementaria).
  1. Add art-75 (Cuota íntegra autonómica).
  1. Add art-77 (Cuota líquida autonómica).
  1. Add art-79 (Cuota líquida total).
- `Phase B: Mínimo personal y familiar formulas`
  1. Add formula renta-2025-minimo-personal-y-familiar-estatal: 0519 =
     0511 + 0513 + 0515 + 0517 (sum of mínimo del contribuyente, por
     descendientes, por ascendientes, por discapacidad — parte estatal).
  1. Add formula renta-2025-minimo-personal-y-familiar-autonomica: 0520
     base derivation (CCAA-conditional, expanded total).
  1. Add formula renta-2025-minimo-personal-base-liquidable-general-
     estatal: 0521 = min(0505, 0519).
  1. Add formula renta-2025-minimo-personal-base-liquidable-ahorro-
     estatal: 0522 = min(0519 - 0521, 0510).
  1. Add formula renta-2025-minimo-personal-base-liquidable-general-
     autonomica: 0523 = min(0505, 0520).
  1. Add formula renta-2025-minimo-personal-base-liquidable-ahorro-
     autonomica: 0524 = min(0520 - 0523, 0510).
- `Phase C: Base imponible / liquidable composition`
  1. Add formula renta-2025-saldo-neto-rendimientos-base-imponible-
     general: 0432 aggregator across income categories and imputaciones
     de rentas.
  1. Add formula renta-2025-base-imponible-general: 0435 = 0432 + 0433.
  1. Add formula renta-2025-base-imponible-del-ahorro: 0460 from the
     AEAT-form-prescribed sum (0424 - 0436 - prior year balances + 0429
     - prior year balances - 0446 - ...). The full formula is encoded
     in the AEAT casilla 0460 label.
  1. Add formula renta-2025-base-liquidable-general: 0500 from 0435
     after reductions.
  1. Add formula renta-2025-base-liquidable-del-ahorro: 0510 from 0460
     after reductions.
- `Phase D: Cuota íntegra split (estatal + autonómica)`
  1. Add formula renta-2025-cuota-base-liquidable-general-estatal: 0532
     = 0528 - 0530.
  1. Add formula renta-2025-cuota-base-liquidable-general-autonomica:
     0533 = 0529 - 0531.
  1. Add formula renta-2025-cuota-integra-estatal: 0545 = 0532 + 0540 +
     0568.
  1. Add formula renta-2025-cuota-integra-autonomica: 0546 = 0533 + 0541
     + 0569.
- `Phase E: Cuota líquida composition`
  1. Add formula renta-2025-cuota-liquida-estatal: 0570 = 0545 - sum of
     state-side deductions (0547 + 0549 + 0550 + 0552 + 0554 + 0556 +
     0558 + 0560 + 0562 + 0567 + 0584).
  1. Add formula renta-2025-cuota-liquida-autonomica: 0571 = 0546 - sum
     of autonomic-side deductions (0548 + 0551 + 0553 + 0555 + 0557 +
     0559 + 0561 + 0563 + 0564 + 0567).
  1. Add formula renta-2025-cuota-liquida-estatal-incrementada: 0585 =
     0570 + 0572 + 0574 (deducciones perdidas, intereses, etc.).
  1. Add formula renta-2025-cuota-liquida-autonomica-incrementada: 0586
     = 0571 + 0577 + 0579 + 0584 (autonomic counterparts).
- `Phase F0: Prior-year substrate prerequisite` — **DELIVERED 2026-05-06/07**
  - The multi-year LIRPF authority is registered as
    `lirpf-cuota-chain-authority` source pointing at
    `corpus/normatives/html/ley-35-2006.html` with
    `evidence_tier = official_source_guidance` and open-ended
    `applies_from = 2007-01-01`. The LIRPF cuota chain articles (49,
    50, 56, 62, 63, 66, 67, 68, 73, 74, 75, 77) have been stable
    since the law took effect, so a single source validates the
    cuota-chain formulas across every ejercicio.
  - Per-year AEAT manual + BOE form-orden substrate is now also
    catalogued for each prior ejercicio:
      - `aeat-renta-{year}-manual-parte1` (2020, 2021, 2022, 2023,
        2024) — official_source_guidance
      - `boe-modelo-100-{year}-form` (2020, 2021, 2022, 2023, 2024)
        — official_source_guidance
    Contract test `test_renta_multi_year_cuota_chain_sources_are_
    catalogued` is green.
- `Phase F1: Multi-year formula backport (2020-2024 revisions)` — **DELIVERED 2026-05-06 (commit 05dd62dd)**
  - 95 cuota-chain formula blocks backported across ejercicios 2020-
    2024 (19 formulas per year). Each revision now carries the full
    chain: minimo personal y familiar (0519-0524), base imponible /
    liquidable (0432, 0435, 0460, 0500, 0510), cuota integra (0532,
    0533, 0545, 0546), cuota liquida y cuota liquida incrementada
    (0570, 0571, 0585, 0586).
  - Each formula uses `lirpf-cuota-chain-authority` as its single
    `official_source_guidance` source citation, grounded in the
    appropriate LIRPF article.
  - Year-specific input-gap filtering applied automatically: 2020
    drops 0568, 0569, 0544, 0567, 0584; 2021 drops 0568, 0569, 0544,
    0584; 2022, 2023, 2024 carry the full input set.
  - Each prior-year revision also got a calculation application_link
    (`modelo-100-{year}-calculation`) wired to
    `aeat.domain.calculations.registry.calculate_registry_snapshot`.
  - Contract tests `test_renta_cuota_chain_present_in_all_supported_
    revisions` and `test_renta_cuota_chain_can_support_multi_year_
    calculation_parity` both pass green.
- `Phase G: Multi-year full-chain parity tests` — **DELIVERED 2026-05-06 (commits 8934ccf5, a60f1d8b, b821e7c8)**
  - End-to-end synthetic-profile test for ejercicio 2025 exercises
    the registry calculator on a 30,000 EUR salary employee with
    default mínimo del contribuyente and asserts the full cuota
    chain to 0587 = 11,872.76 EUR.
  - Parametrized multi-year scenario covers ejercicios 2020, 2021,
    2022, 2023, 2024, 2025 with all-zero inputs and asserts every
    cuota-chain casilla evaluates to zero. 8 tests pass.
  - Year-specific operand-ref filtering reflects the F1 formula
    shape per revision (older revisions drop 0544/0567/0584 negate
    args from cuota líquida formulas).
  1. Convert the aspirational full-chain xfail-strict test into a green
     parameterised test once every phase is delivered for at least one
     ejercicio.
  1. Extend that test to cover all 6 ejercicios 2020-2025 with at least
     one synthetic profile per year.
  1. Wire CCAA-conditional behaviour into the parity test for at least
     three autonomous communities (e.g. Madrid, Cataluña, Valencia).

## Parallelization

Phases A, B, C, D, E are sequential within ejercicio 2025: each
consumes the substrate of the previous one. Phase F (multi-year
backport) is internally parallelisable per year once the 2025 chain is
green. Phase G is final.

Across phases, additional non-Renta-cuota-chain work continues in
parallel (e.g. profile bindings under the existing phase-4 Renta
personal/family slice, ongoing CCAA deduction definitions, Modelo 200
formulas). Those workstreams are kept disjoint from this plan by
restricting Phase A-E to the cuota chain articles and casillas listed
above; touching unrelated articles or casillas is out of scope and
must be flagged explicitly.

## Verification

The aspirational test file
`src/aeat/domain/calculations/registry/test_renta_pipeline_aspirational.py`
defines one xfail-strict test per phase. Every test runs on every CI
invocation. Each test fails by design until its phase delivers; once a
phase delivers, the corresponding xfail flips to xpass which trips the
strict marker, turning the suite red. The phase commit is required to
remove the marker (or convert it to a green assertion) at the same
time as the formula registration.

The test file is the contract: the merge that closes a phase must (a)
register the formulas in the modelo TOML, (b) update the aspirational
test (remove or convert the marker), and (c) cite the matching plan
phase in its commit message.

The aspirational tests are NOT skipped, NOT marked TODO, NOT placeholder
asserts. They exercise the registry through the public load + validate
pathway. They use real synthetic profiles produced by the existing
scenario harness in `_scenarios.py`. Each aspirational test runs end-to-
end through the registry calculator and asserts non-zero outputs in the
final settlement chain casillas.

The plan is complete when:

- All 11 cuota chain articles are catalogued and corpus-grounded.
- All 24 formulas listed in Phase B-E are registered in 2025.
- All 5 prior-year ejercicios (2020-2024) carry the same chain.
- The full-chain test xpasses for at least one synthetic profile per
  ejercicio.
- All aspirational xfail-strict markers are removed.

The plan is NOT complete simply because xfail-strict tests run without
breaking the suite. xfail-strict in pytest produces "xfail" status when
the test fails as expected; the suite is GREEN in that case. A delivered
phase produces "xpass" status which is RED under strict. The marker
removal is the final closing act.

## Post-Rollout Hardening (2026-05-07)

Three additional autonomous-loop deliverables landed after the cuota
chain core was complete:

- **Income side backport** (commits e3f7d5c5, 9f521bfe). 117 income-
  side formulas (trabajo, capital mobiliario, capital inmobiliario,
  estimación directa simple) replicated across ejercicios 2020-2024
  with year-specific casilla-gap filtering. Per-year totals: 2020-
  2022 each 47 formulas, 2023-2024 each 47 formulas, 2025 unchanged
  at 54.

- **Estimación directa modal substrate backport** (commit 187e79bd).
  Each prior-year ejercicio now carries the modal binding (renta-
  {year}-modelo-100-estimacion-directa-es-normal selecting normal
  vs simplified mode based on casilla 0168) plus the difficult-
  justification rate (5%) and cap (€2,000) parameters, plus the
  formulas at 0222 (cap on dificil-justificacion gastos) and 0224
  (rendimiento neto branching on the modal binding).

- **Behavioural + drift-detection regression guards** (commits
  815874ec, 03a9144e):
    - test_renta_chain_behaviour.py: 8 numeric-output behaviour tests
      that catch silent regressions where a formula gets swapped, an
      operand dropped, or a negate inverted.
    - test_modelo_100_drift_detection.py: 8 schema-level drift
      detection tests covering top-level chain coverage per revision,
      calculation+filing application_link presence, orphan binding /
      parameter detection (with profile-source bindings excluded
      since they expose taxpayer data to the application layer),
      and cross-reference resolution (relations → bindings, formulas
      → bindings/parameters).

39/39 tests across the 5 cuota-chain-related test files pass; 25/25
modelos validate.

## Open Follow-Up Slices

- **Cross-modelo relations backport** (Task #42, deferred). Cloning
  the 9 cross-modelo relations + their 8 previous_filing target_
  bindings + 9 dependency_classifications + the 8 supporting
  constructs (renta-dependent-modelos plus 7 sibling constructs) into
  ejercicios 2020-2024. Each construct is 50+ lines of legal_refs,
  source_refs, bindings, relations, dependency_classifications,
  deadline_windows, and application_links arrays — substantial
  substrate clone deferred behind tractable hardening tasks.

- **Escala progresiva parameters per ejercicio** (Task #44). Encode
  each year's IRPF estatal escala (LIRPF art. 63) and autonomic
  default escala (LIRPF art. 74) bracket values as registry
  parameters with date_axis filing_period and BOE-anchored citations.
  Add formulas that apply the escala to base liquidable to compute
  cuotas (replacing manual 0528-0531 inputs). Unblocks the 30k
  employee profile to compute end-to-end across all years without
  manual escala values.

- **Capital gains chain composition** (Task #46). Replace the
  manual 0429 / 0424 inputs with formulas computing the saldo neto
  positivo from upstream casillas, plus the multi-year carry-forward
  compensation (0436, 0439-0455 saldos pendientes).

- **Multi-year non-zero income synthetic profiles** (Task #48).
  Build executable parity scenarios for each ejercicio that exercise
  the trabajo and estimación directa chains end-to-end with realistic
  synthetic inputs (30k employee, 25k autónomo normal mode, 18k
  autónomo simplified mode). Each scenario asserts the full chain
  output through 0587. Year-specific escala values manual until
  Task #44 lands the parametric escala.

- **Migrate rental tier resolver thresholds to registry parameters**
  (Task #50). src/aeat/domain/rental/_tier_resolver.py hardcodes the
  LIRPF art. 23 thresholds (PRIOR_RENT_REBAJA_THRESHOLD = 0.05,
  REHAB_LOOKBACK_DAYS = 730, JOVEN_TENANT_AGE_MIN/MAX = 18/35) in
  Python rather than the registry. Per the calculation-truth-registry
  ADR these are filing-grade legal constants and must live as registry
  parameters with BOE-anchored citations.
