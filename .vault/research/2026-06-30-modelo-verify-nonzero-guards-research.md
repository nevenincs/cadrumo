---
tags:
  - '#research'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-adr]]"
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
  - "[[2026-06-19-m202-first-period-attestation-adr]]"
---

# `modelo-verify-nonzero-guards` research: `closing silent-under-declaration gaps on unguarded manual-base modelos`

## Problem Statement

The `aeat` CLI `prepare → calculate → verify` workflow is the surface an autonomous LLM tax-advisor agent drives (`2026-06-30-agent-harness-adr`). The verify gate's Layer-2 structural-invariant check — `VerificationPredicateDefinition.verification_predicates` declared per revision, evaluated by `_evaluate_predicate_expression` in `src/aeat/application/modelo/_verification_actions.py:306` — currently exists for only 6 of the ~12 calc-grade modelos that have a manual or partially-manual base chain: M100, M130, M131, M200, M210, M303. Confirmed by a global sweep `rg -l "verification_predicates" src/aeat/_data/registry/aeat/modelos --type toml`, which returns exactly 11 files across those 6 modelos and no others. M202, M123, M151, and M714 ship zero `verification_predicates` entries at HEAD. A `verification_expectations` block exists for M202 (all three revisions) but is the workbook-parity schema (`computed_casilla_ids` / `tolerance` / `discrepancy_causes`), a structurally distinct TOML key from `verification_predicates` (confirmed in `_schema.py:1046-1160`: both are separate `ModeloRevision` fields). For these modelos a positive economic input (resultado contable, base imponible, rendimientos, valuation) can resolve to a zero downstream base/cuota and the verify gate grants `verified_complete` with `finding_count = 0` — the exact defect class `no-silent-under-declaration` closes for M200 and M131.

## Method

Per `registry-revision-content-inline-or-fragmented`, every revision was checked for BOTH inline `revision.toml` declarations and fragmented `casillas/`, `formulas/`, `bindings/`, `verification_expectations/` subdirectories before concluding gap or non-gap. The vaultspec-rag service was unavailable this session (server reported stopped, then port 8766 already bound by a peer process at start time) — discovery was performed via direct Glob/Read/Grep against the registry tree at HEAD instead, exhaustive for the five target modelos' single-digit revision counts.

## The predicate DSL (confirmed contract)

`VerificationPredicateDefinition` (`src/aeat/domain/calculations/registry/_schema.py:1046`): `predicate_id`, `legal_refs` (must resolve in the legal catalogue), `expression` (a string matched against `KNOWN_VERIFICATION_PREDICATE_OPERATORS`, `_schema.py:1011`), `finding_kind: Literal["BLOCKING_RULE","ADVISORY"]` (default `BLOCKING_RULE`). Registry-build validation (`_validate_surfaces.py:196-249`, `validate_verification_expectation_section`) checks only: (1) every `predicate.legal_refs` id resolves against the legal catalogue, (2) every casilla id referenced in the expression exists in the revision's casilla set, (3) the operator name is known. No construct/binding coverage sweep applies to `verification_predicates` — `ConstructDefinition` (`_schema.py:643`) has no `verification_predicates` field, unlike `casilla_ids`/`formulas`/`bindings` membership which the `casilla-grounding-corrects-actividades-default-by-section` three-layer coverage check governs. So every proposed predicate below is a pure registry-authoring addition: no construct or binding `legal_refs` sweep is required.

`implies_nonzero(["antecedent_id", "consequent_id"])` (the operator used in every recommendation): holds iff `casilla_values[antecedent] <= 0` OR `casilla_values[consequent] != 0`. A missing consequent evaluates to `Decimal(0)`. Evaluator: `_evaluate_predicate_expression`, `_verification_actions.py:306-450`. ADVISORY dispatch fires a WARNING-severity finding when the negative-logic condition is met (`_verification_actions.py:578-648`); the verified-complete grant is unaffected by WARNING findings, only by `BLOCKING_RULE` (`_verification_actions.py:1352-1361`).

## Reference patterns (do not modify; cited as templates)

- **M200** (`src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/verification_expectations/0001-verification_predicates.toml`): two ADVISORY guards on the IS result chain (`implies_nonzero(["00500","00501"])`, `implies_nonzero(["00501","DP200014:00552"])`), two BLOCKING_RULE BIN-compensation caps, one ADVISORY dotaciones-deterioro carry, one ADVISORY `roll_forward_balances` continuity check. Decision record: `2026-06-02-modelo-200-base-determination-adr`. Test: `src/aeat/domain/calculations/registry/tests/test_modelo_200_registry.py:443-492`.
- **M131** (`.../131/revisions/2024/verification_expectations/0002-verification_predicates.toml`): one BLOCKING_RULE cap (`cap_le_when_positive(["11","10"])`), one ADVISORY `implies_nonzero(["01","02"])`. Test (two-tier, the fuller template): `src/aeat/application/modelo/tests/test_verification_m131_advisory.py` — loads the predicate off `resources().modelos.authority`, asserts legal_refs membership, then calls `evaluate_verification_predicates((predicate,), casilla_values, profile)` directly to prove FIRES (positive antecedent, zero consequent → 1 ADVISORY/WARNING finding) and HOLDS (positive antecedent, positive consequent → no finding), parametrized across all four M131 revisions.

Both share the shape this research follows: the "second manual stage" pattern (M200's 00500→00501, two independently-skippable manual casillas) versus the "formula-defended but still worth declaring" pattern (M131's 01→02, where the scale minimum makes the implication mechanically near-certain but the registry still declares it as defence-in-depth and explicit legal-invariant documentation).

## M202 — priority, full chain traced

All three revisions (`2019-2022`, `2023-2024`, `2025-y-siguientes`) are fragmented and none carry any `verification_predicates`. `2025-y-siguientes` was read verbatim end to end; `2019-2022` and `2023-2024` were confirmed to carry an identically-named, identically-numbered file/casilla-id structure (e.g. `casillas/0004-04.toml`, base-imponible-previa formula with `target_casilla_id = "13"` in all three) but their formula expressions were NOT independently re-read verbatim — flagged as an open item for the plan phase.

**Modalidad 40.3 chain** (LIS art. 40.3 base method, mandatory for INCN > €6M, optional otherwise): `04` (resultado contable después del IS, MANUAL, required=false) → `38`=05+67+07 → `39`=06+37+08 → `13`=04+38-39 (base imponible previa, FORMULA) → `16`=max(0,13-44-14+45-46) → `18` → `32` → `34`=max(32,33). (`formulas/0001`–`0008`, `2025-y-siguientes`.)

**Modalidad 40.2 chain** (default for INCN ≤ €6M): `01` (Base del pago fraccionado, BOUND, source=relation_prefill, selector={source_modelo:"200", source_casilla_id:"DP200014B:00592"}) → `03`=(01×18%)-02. `02` is BOUND (prior M202 casilla `34`). Modality split is INCN-driven (`derive_modelo_202_modality`, `_applicability_modelo202.py:115`) from a `profile`-kind binding that fails closed when undeclared (`_modelo_202_incomplete_modality_finding`, `_verification_cross_period.py:125-149`).

**Already-closed risk (do not re-guard):** the 40.2 lane's `01` binding documents a zero-carry for a first-year filer with no prior M200 cuota; this cross-modelo dependency is already enforced fail-closed by the cross-period clean-state gate (`_cross_period_clean_state.py:395-494`, `modelo_202_modality`), suppressed only for a genuine first-IS-year filer under `ART_40_2_OPTIONAL` (`2026-06-19-m202-first-period-attestation-adr`). Different mechanism from the `verification_predicates` DSL — out of scope here.

**Open question — casilla `33`:** "Mínimo a ingresar (CN >= 10 millones euros)" (`casillas/0049-33.toml`) is entirely MANUAL with no formula deriving the LIS art. 40.3 floor. Not addressable by a predicate (no clean antecedent casilla — the floor depends on a cifra-de-negocios profile fact and a percentage parameter not wired into a formula). A calculation-modelling gap analogous to the M200 ADR's Phase 2, out of scope for an advisory predicate.

**Open question — B2 lane:** casillas `61`–`66` ("Mod. 40.3 LIS B2 — casos específicos", grupos fiscales) not investigated this pass.

**Recommended guard:** `implies_nonzero(["04", "13"])`, ADVISORY. `13` is currently fully formula-derived from `04` (so the implication holds automatically except when `38`/`39` corrections exactly offset `04`), but this mirrors the M200 dotaciones/BIN-continuity precedent of declaring structural invariants defensively and gives an explicit, legally-grounded statement of the modalidad 40.3 relationship that is otherwise implicit only in formula composition (a future registry edit decoupling `13` from `04` would silently re-open the M200-class gap with no test failing it).

**Legal grounding (confirmed, reviewed, corpus-backed):** `ley-27-2014:art-40-3` (`legal/is.toml:556-574`, `corpus_ref = "corpus/normatives/html/ley-27-2014-art-40.html#a40"`, reviewed 2026-05-26, `required_text` includes "modalidad... importe neto de la cifra de negocios haya superado la cantidad de 6 millones de euros"); `ley-27-2014:art-40` (`is.toml:533-554`, same corpus file, reviewed 2026-05-05, already cited on every M202 casilla in this chain).

## M123 — IRPF retenciones capital mobiliario

`2024-y-siguientes` is fragmented and calc-grade (`verification_expectations/` present but empty of `verification_predicates`). `2019-2023` was checked both inline (no casillas block) and fragmented (no casillas/formulas subdir) — genuinely parse-only / historical, no calc chain to guard.

Chain (`casillas/0001-casillas.toml`, `formulas/0001-formulas.toml`): `01`+`02` (números rentas, MANUAL) → `03` (total rentas, FORMULA); `04`+`05` (bases, MANUAL) → `06` (base total, FORMULA); `07`+`08` (retenciones, MANUAL) → `09` (retenciones total, FORMULA); `09`+`11` → `12` → `14` (resultado a ingresar). M123 is filed by the PAYER withholding IRPF on capital-mobiliario income; the retention rate is a fixed statutory percentage (19%, with a documented capital-semilla reduction that still leaves a positive rate) — no documented "base positive, retención legitimately zero" case within these categories.

**Recommended guard:** `implies_nonzero(["06", "09"])`, ADVISORY (base total implies retenciones total nonzero), the single-pair aggregate shape mirroring M131. A higher-precision per-category alternative (`04→07` + `05→08`) was considered but not recommended without confirming no category-level legitimate zero-retention case exists — flagged as an open design choice for the plan phase.

**Legal grounding (confirmed, reviewed, corpus-backed):** `rd-439-2007:art-90` (`legal/irpf.toml:177-195`, `corpus_ref = "corpus/normatives/html/rd-439-2007-art-90.html#a90"`, reviewed 2026-05-15, notes name "Base reglamentaria de la retención sobre rendimientos del capital mobiliario en Modelo 123 ... y Modelo 193", `required_text` includes "19 por ciento"); `ley-35-2006:art-101` (`irpf.toml:2781-2799`, reviewed 2026-05-15, already cited on every M123 casilla).

## M151 — IRPF régimen impatriados (Ley Beckham)

Single revision `2015-y-siguientes`, fragmented (no `verification_expectations/` directory yet). Chain: `impatriado.base-liquidable-general` (MANUAL) → `impatriado.cuota-integra-general` (FORMULA, lookup_bracket against `modelo-151.escala-cuota-integra-general`, 24% to €600k / 47% above) → `impatriado.cuota-diferencial` (= cuota_integra - retenciones). `impatriado.retenciones` is a parallel manual credit (a zero withholding credit is legitimate, not an implication target). Any positive base produces a strictly positive cuota mechanically (the 24%/47% escala has no 0% band), the same defensive/declarative shape as M202's `04→13` since `cuota-integra-general` has no independent manual override.

**Recommended guard:** `implies_nonzero(["impatriado.base-liquidable-general", "impatriado.cuota-integra-general"])`, ADVISORY.

**Legal grounding (confirmed, reviewed, corpus-backed):** `ley-35-2006:art-93` (`legal/irpf-impatriados.toml:11-28`, `corpus_ref = "corpus/normatives/html/ley-35-2006-art-93.html#art-93"`, reviewed 2026-05-27, already cited on both casillas).

## M714 — Impuesto sobre el Patrimonio

Single revision `2021-y-siguientes`, fragmented. The registry's own authoring comment states: "Base inputs, límite conjunto, total cuota íntegra, cuota minorada, and cuota a ingresar stay manual until their own official formula evidence lands." This is the least-modelled of the five — multiple sequential manual casillas with no formula linkage, the closest analogue to M200's pre-ADR state. Chain: `patrimonio.base-imponible` (MANUAL) → `patrimonio.base-liquidable` (MANUAL, not formula-derived) → `patrimonio.cuota-integra` (29, FORMULA, lookup_bracket, escala estatal art. 30); then `limite-conjunto` (33, MANUAL), `reduccion-limite-80` (39, FORMULA=cuota-integra×80%), `total-cuota-integra` (40, MANUAL), `cuota-minorada` (45, MANUAL), `cuota-a-ingresar` (55, MANUAL, headline final figure).

**Recommended guard:** `implies_nonzero(["patrimonio.cuota-integra", "patrimonio.total-cuota-integra"])`, ADVISORY. `cuota-integra` (29) is formula-derived from `base-liquidable` (no manual override); `total-cuota-integra` (40) is the pure administrative-transcription sum step before the límite-conjunto reduction — no legitimate reason for it to be zero when `29` is positive.

**Explicitly rejected candidates (open questions, NOT recommended without further tax-expert grounding):** `base-imponible → base-liquidable` — the mínimo exento (€700,000 state default) means a filer can legitimately have positive gross `base-imponible` (still obligated to file, since the threshold triggers on gross assets ≥ €2M) with a zero/floored `base-liquidable`; common, not exceptional; materially high false-positive risk. `total-cuota-integra → cuota-a-ingresar` — the límite-conjunto (art. 31, 60% cap, 20% floor), Ceuta/Melilla bonificación (75%), and foreign-tax-credit deductions create multiple legitimate full/near-full offset paths not yet modelled; requires deeper legal nuance than this pass affords.

**Legal grounding (confirmed, reviewed, corpus-backed):** `ley-19-1991:art-30` (`legal/patrimonio.toml:30-48`, `corpus_ref = "corpus/normatives/html/ley-19-1991-art-30.html#art-30"`, reviewed 2026-06-02, notes "Base de la tarifa del Modelo 714", already cited on both casillas).

## M210 — IRNR (ADDED predicate, not a new file)

Single revision `2025`, fragmented. **Correction to task hypothesis:** the existing `verification_expectations/0001-verification_predicates.toml` carries exactly ONE predicate at HEAD (`m210-representante-fiscal-required`, BLOCKING_RULE, TRLIRNR art. 10) — not two. Chain: `rendimientos_integros` (MANUAL, required=true) and `gastos_deducibles` (MANUAL, required=false), plus the inmobiliaria inputs (`valor_catastral` / `coeficiente_imputacion_inmobiliaria` / `dias_imputacion` / `valor_adquisicion` / `valor_comprobado_administracion`, all MANUAL required=false, meaningful only when `tipo_renta="inmobiliaria"`) → `base_imponible` (COMPUTED via custom op `m210_resolve_base_imponible`, branching on `tipo_renta`) → `tipo_gravamen` → `cuota_integra` → `cuota_diferencial`.

**Recommended, ready-to-author guard:** `implies_nonzero(["rendimientos_integros", "base_imponible"])`, ADVISORY — covers the general/UE branch (where `rendimientos_integros` is required=true). Legitimate zero-base exception: full Art. 24.6 UE/EEE `gastos_deducibles` offset.

**Open question — NOT ready to author (highest real-world value, requires DSL extension):** the inmobiliaria branch (a non-resident owning Spanish real estate with no rental income still owes imputed-income IRNR annually) is one of the most common M210 scenarios. An operator selecting `tipo_renta = "inmobiliaria"` but leaving `valor_catastral` blank produces a silent zero base — the exact under-declaration class targeted — but no existing predicate operator can express it: `implies_nonzero` needs a numeric antecedent, while this antecedent is a categorical equality (`tipo_renta == "inmobiliaria"`). `profile_field_required` is the nearest existing shape but reads profile fields, not same-modelo casilla values, and checks presence not numeric nonzero. Closing it requires either a new DSL operator (e.g. `casilla_equals_implies_nonzero(["antecedent","literal","consequent"])`) or modelling `tipo_renta` as a typed enum casilla with applicability wiring outside the predicate layer. The single highest-priority open item across this research.

**Legal grounding (confirmed, reviewed, corpus-backed):** `trlirnr-rdleg-5-2004:art-24` (`legal/irnr.toml:60-74`, `corpus_ref = "corpus/normatives/html/trlirnr-rdleg-5-2004.html#a24"`, reviewed 2026-05-27, notes name "Fundamento de la base imponible M210 casillas rendimiento_integro y gastos_deducibles").

## Test design (per `no-tautological-calculation-tests`)

Every proposed predicate is a structural/gate-behaviour test, not a hand-computed Decimal oracle. Two-tier pattern mirroring `test_verification_m131_advisory.py`:
1. **Registry-shape test** (per `tests-live-under-domain-tests-folders`, `src/aeat/domain/calculations/registry/tests/test_modelo_<id>_registry.py` or a new file per the M200 pattern): load the snapshot via `build_snapshot`/`resources().modelos.authority`, assert `predicate_id`/`expression`/`finding_kind` exist on `revision.verification_predicates`, assert the grounding legal_ref is present.
2. **Gate-behaviour test** (`src/aeat/application/modelo/tests/test_verification_m<id>_advisory.py`): call `evaluate_verification_predicates((predicate,), casilla_values, profile)` (`_verification_actions.py:648`) with antecedent positive/consequent zero → exactly one ADVISORY/WARNING finding (FIRES); antecedent positive/consequent positive → no findings (HOLDS); antecedent zero or negative/consequent zero → no findings (trivial HOLD, no false positive on a filer with no relevant activity in that lane).

## Open items not investigated (explicit, per task bound)

- M202 `2019-2022` / `2023-2024` formula text verbatim re-confirmation.
- M202 B2 grupos-fiscales casillas (61–66) economic-risk assessment.
- M123 per-category (`04→07`, `05→08`) vs aggregate (`06→09`) design choice.
- M714 `base-liquidable` and `cuota-a-ingresar` edges (deliberately not recommended; flagged for expert review, not authored).
- M210 inmobiliaria-branch categorical-conditional predicate DSL extension.
