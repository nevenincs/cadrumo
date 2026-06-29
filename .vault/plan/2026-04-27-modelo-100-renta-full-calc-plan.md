---
tags:
  - '#plan'
  - '#modelo-100-renta-full-calc'
date: '2026-04-27'
modified: '2026-06-13'
related:
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-research]]"
  - "[[2026-04-21-modelo-100-renta-plan]]"
---



# `modelo-100-renta-full-calc` implementation plan

Megaproject implementation plan for the full-form Modelo 100 (RENTA /
IRPF anual) calc-verify-roundtrip universe across 2024 / 2025 / 2026.
Closes `#317` / `#341` / `#342` / `#343` / `#344` per the user's
2026-04-27 directive. Executes the architectural commitments captured
in the companion ADR.

## Proposed Changes

Author a sub-package `src/aeat/domain/formulas/_rulesets/modelo_100/` hosting
per-anexo per-año modules covering the full RENTA universe: anexos A,
B1, B2, C, D (three régimenes), E, F, G, Ñ; tax years 2024, 2025, 2026;
15 ordinary CCAAs + Ceuta/Melilla art. 68.4 60%. Aggregate per-año
files (`modelo_100_2024.py`, `_2025.py`, `_2026.py`) compose anexo
modules into `RULESET` constants and register at default variant slots
(`modelo_100.<año>`). Co-located tests per anexo per año. Pydantic v2
amortización + inventario surfaces. Per-CCAA closed `StrEnum` + per-CCAA
tarifa autonómica brackets. Multi-anexo borrador extractor extension
preserving the unique `--from-borrador` dispatch. Synthetic generator
extension for full-form layout. Kent integration test extension.
`.vault/reference/2026-04-27-modelo-100-rule-delta-reference.md`
manifest. `docs/coverage/modelos.md` row flip.

## Tasks

Phased waves; each wave's commit set is independently green. The draft
PR opens after Wave 5 (Anexo A+B1 complete) and updates per wave. Per-
wave audit checkpoint + (after waves 5/7/9/11) multi-agent code review
pass.

### Wave 5 — sub-package scaffolding + Anexo A + Anexo B1 (rendimientos del trabajo)

5.1. Create `src/aeat/domain/formulas/_rulesets/modelo_100/` sub-package skeleton:
     `__init__.py` (exports), `_common.py` (`_label`, shared citation
     helpers), `_ccaa.py` (`CCAA` closed `StrEnum`, per-CCAA tarifa
     placeholders for Madrid + Cataluña + Andalucía + Comunitat
     Valenciana + Castilla y León).
5.2. Author `modelo_100/_amortization.py` (Pydantic
     `AmortizationCategory` + `AssetClass` enum + LIS art. 12.1.a)
     table verbatim — ~30 entries).
5.3. Author `modelo_100/_inventario.py` (Pydantic `InventoryRecord` +
     `ValuationMethod` enum FIFO/PMP/COSTE_MEDIO, LIFO forbidden by
     construction).
5.4. Author `modelo_100/anexo_a_<año>.py` for 2024 / 2025 / 2026
     (datos personales casillas — identification only, no computed).
5.5. Author `modelo_100/anexo_b1_<año>.py` for 2024 / 2025 / 2026
     (rendimientos del trabajo: arts. 17-20 LIRPF; art. 19 gastos
     deducibles; art. 18 reducción 30% irregularidad; art. 20
     reducción rendimientos del trabajo with the 14.852/17.673,52/
     19.747,50 thresholds; ~25 casillas per año).
5.6. Author per-año aggregator `modelo_100_<año>.py` for 2024 / 2025 /
     2026 — composes Anexo A + B1 into `RULESET` constants. (The
     aggregator grows as later waves land more anexos.)
5.7. Register `MODELO_100_2024 / _2025 / _2026` in
     `src/aeat/domain/formulas/_rulesets/__init__.py` (default variant).
5.8. Author co-located tests `modelo_100/test_anexo_b1_<año>.py` —
     module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`;
     external-anchored worked example per LIRPF art. 20; threshold-edge
     at the four art. 20 reducción brackets; zero-boundary; per-año
     no-drift regression.
5.9. Bump mutation harness `EXPECTED_COUNTS` in
     `test_mutator_kill_rate.py` for the three new M100 rulesets'
     Anexo B1 nodes.
5.10. Open draft PR via `gh pr create --draft`. Title:
     `feat(formulas,declaracion,tests): MEGAPROJECT — Modelo 100 RENTA
     full-form calc-verify-roundtrip 2024/2025/2026 (#317, #341, #342,
     #343, #344)`. Body cites parent EPIC `#316` + sibling Tier-L refs
     + ADR + research + plan. Include `Closes #317 #341 #342 #343 #344`
     trailer (effective when promoted to ready).
5.11. Audit checkpoint: `aeat audit rulesets citations` 100% on M100
      WIP; `just lint && just typecheck && just hooks` green;
      `just test src/aeat/domain/formulas/_rulesets/modelo_100/` green;
      mutation kill-rate ≥ 90% on new M100 nodes.
5.12. Per-wave exec record under
      `.vault/exec/2026-04-27-modelo-100-renta-full-calc/wave-5-anexo-a-b1-exec.md`.

### Wave 6 — Anexo B2 (capital mobiliario) + Anexo C (capital inmobiliario)

6.1. Author `modelo_100/anexo_b2_<año>.py` for 2024 / 2025 / 2026
     (LIRPF arts. 25-26: dividendos, intereses, gastos administración;
     reducción art. 26 30% irregularidad).
6.2. Author `modelo_100/anexo_c_<año>.py` for 2024 / 2025 / 2026
     (LIRPF arts. 22-24: alquileres, gastos deducibles, amortización
     3% construcción, reducción tiered 50/60/70/90% post-Ley 12/2023;
     LIRPF art. 85 imputación rentas inmobiliarias).
6.3. Co-located tests per anexo per año with external-anchored worked
     examples + threshold-edge cases.
6.4. Update per-año aggregator imports.
6.5. Mutation harness EXPECTED_COUNTS bump.
6.6. Audit checkpoint + exec record.

### Wave 7 — Anexo D (actividades económicas) — biggest wave

7.1. Author `modelo_100/anexo_d_normal_<año>.py` for 2024 / 2025 / 2026
     (LIRPF art. 28 + LIS reference: P&L casillas, ingresos/gastos
     explotación, variación existencias via `InventoryRecord`,
     amortizaciones via `AmortizationCategory` table, provisiones,
     deducciones por inversiones).
7.2. Author `modelo_100/anexo_d_simplificada_<año>.py` for 2024 / 2025 /
     2026 (RIRPF art. 30 — gastos de difícil justificación encoded as
     `min_op(percent(rate_param, rendimiento_neto_pos), cap_param)`;
     current non-exception revisions use 5%/2.000€, while DA 56 keeps
     2023 as a distinct 7% revision).
7.3. Author `modelo_100/anexo_d_modulos_<año>.py` for 2024 / 2025 /
     2026 (RIRPF arts. 32-35 — módulos verification chain; 2026 module
     references Orden HAC/1425/2025 (`BOE-A-2025-25272`) for módulos
     values).
7.4. Co-located tests per régimen per año.
7.5. **Pause for rolling audit + multi-agent review pass** (gemini +
     codex + claude). This wave is the most complex; reviews catch
     drift early.
7.6. Audit checkpoint + exec record.

### Wave 8 — Anexo E (ganancias y pérdidas) + Anexo F (bases + mínimos)

8.1. Author `modelo_100/anexo_e_<año>.py` (LIRPF arts. 33-39: ganancias/
     pérdidas patrimoniales; FIFO acciones art. 37; saldos a integrar
     en base general/ahorro).
8.2. Author `modelo_100/anexo_f_<año>.py` (LIRPF arts. 47-61: base
     imponible general + ahorro; reducciones planes pensiones art. 51,
     tributación conjunta art. 84; mínimos personal/familiar arts. 56-61
     with the 5.550/2.400/2.700/4.000/4.500/2.800/1.150/1.400/3.000/
     9.000/3.000 €amounts).
8.3. Co-located tests with mínimo-personal threshold cases (>65, >75,
     descendientes 1º through 4º+, <3 años bonus, ascendientes
     >65/>75, discapacidad 33-65%/≥65%/asistencia).
8.4. Mutation harness EXPECTED_COUNTS bump.
8.5. Audit checkpoint + exec record.

### Wave 9 — Anexo G (cuotas, escalas, deducciones estatales)

9.1. Author `modelo_100/anexo_g_<año>.py` for 2024 / 2025 / 2026:
     - Cuota íntegra estatal general — `BracketsFormula` with LIRPF
       art. 63 brackets (12.450/20.200/35.200/60.000/300.000 € at
       9,5/12/15/18,5/22,5/24,5%; stable 2024-2026).
     - Cuota íntegra estatal del ahorro — `BracketsFormula` with LIRPF
       art. 66 brackets; **2024 top 14% / combined 28%** vs **2025-2026
       top 15% / combined 30%** (Ley 7/2024).
     - Cuota íntegra autonómica general — per-CCAA `BracketsFormula`
       for Madrid + Cataluña + Andalucía + Comunitat Valenciana +
       Castilla y León. The other 10 CCAAs use the LIRPF art. 74
       default tarifa unless their texto refundido overrides (encode
       once per CCAA).
     - Cuota líquida estatal (LIRPF art. 67) and autonómica (art. 77).
     - Cuota diferencial (art. 79).
     - State deductions (LIRPF arts. 68-69, 80-81 bis): vivienda
       habitual transitoria, donativos Ley 49/2002, alquiler vivienda
       transitoria, maternidad art. 81, familia numerosa art. 81 bis.
     - **Ceuta + Melilla 60% reducción** (LIRPF art. 68.4 post Ley
       6/2018) as casilla `0612_CEUTA_MELILLA` —
       `percent(lit("0.60"), <cuota proporcional>)`.
9.2. Co-located tests with full per-año tarifa worked examples
     external-anchored to the BOE consolidated text article numbers.
9.3. Threshold-edge cases at every bracket boundary (12.449,99 vs
     12.450,01; 20.199,99 vs 20.200,01; etc.).
9.4. **Multi-agent review pass** triggered after Anexo G lands —
     gemini + codex + claude.
9.5. Audit checkpoint + exec record.

### Wave 10 — Anexo Ñ (deducciones autonómicas) — 15 CCAAs × 3 años

10.1. Author `modelo_100/anexo_n_<año>.py` for 2024 / 2025 / 2026 with
      per-CCAA aggregate-deduction casillas (`0622_AND`, `0622_ARA`,
      `0622_AST`, `0622_BAL`, `0622_CAN`, `0622_CAT`, `0622_CLM`,
      `0622_CYL`, `0622_CTL`, `0622_VAL`, `0622_EXT`, `0622_GAL`,
      `0622_MAD`, `0622_MUR`, `0622_RIO`).
10.2. For each CCAA, encode the per-deduction casillas + formulas per
      the research §6.2 catalogue. Casilla naming
      `D_<CCAA3>_<DEDUCTION_SLUG>` (e.g. `D_MAD_NACIMIENTO_HIJO`).
10.3. CCAA-aggregate casilla formula: `add_op` over all per-deduction
      casillas for that CCAA.
10.4. State-level `0622` (deducciones autonómicas total) =
      `add_op(0622_AND, 0622_ARA, ..., 0622_RIO)` — 15 operands.
10.5. **2026 baseline strategy** — for the 14 CCAAs without published
      2026 Ley de Presupuestos, encode 2025 values as 2026 baseline
      with citation `quoted_text_es` annotation noting "valor heredado
      de 2025 al no haberse publicado modificación BOE para ejercicio
      2026 a fecha 2026-02-28". Andalucía's 2026 deltas (Ley 8/2025)
      land verbatim.
10.6. Co-located tests per CCAA per año — at minimum: per-CCAA
      consistent-aggregate test + zero-boundary; the 5 highest-
      population CCAAs get external-anchored worked examples per
      AEAT manual práctico.
10.7. Mutation harness EXPECTED_COUNTS bump (significant — ~336
      deduction × 3 año aggregation + bracket nodes).
10.8. **Multi-agent review pass** after Anexo Ñ lands.
10.9. Audit checkpoint + exec record.

### Wave 11 — synthetic generator + multi-anexo extractor + integration test

11.1. Extend `Modelo100GenParams` `_BOXES` for full-form layout;
      multi-page generator emits Anexo A + B1 + B2 + C + D + E + F +
      G + Ñ casillas.
11.2. Author 3 new borrador extractors: `Modelo100V2024Extractor`,
      `Modelo100V2025Extractor`, `Modelo100V2026Extractor` in
      `src/aeat/adapters/inbound/borrador/_extractors/`. Existing
      `Modelo100SummaryV2025Extractor` retained for the summary path.
11.3. Round-trip: `generator(params) → PDF → borrador extractor →
      casilla map == expected_casillas` for at least one full-form
      case per año.
11.4. Extend `tests/integration/test_kent_workflows.py` with sibling
      `TestKentImportsModelo100FullBorrador` class — per-año
      parametrize cases + ES-default + EN-explicit; 3 mandatory cases
      (happy EN / happy ES / drift NEEDS_REVIEW) + optional 4th
      (discrepancy classifier). Marker:
      `[pytest.mark.unit, pytest.mark.domain_submission, pytest.mark.fixture_tier_l3]`.
11.5. Audit checkpoint + exec record.

### Wave 12 — multi-agent code review pass (final, comprehensive)

12.1. Push to draft PR.
12.2. Wait for `gemini-code-assist` auto-review on full diff.
12.3. Dispatch codex review subagent with full-diff scope.
12.4. Dispatch claude review subagent (`vaultspec-code-reviewer`) with
      full-diff scope.
12.5. Address findings from all three streams.
12.6. Document sign-offs + findings in PR body.
12.7. Per-wave exec record captures the cross-perspective review
      summary.

### Wave 13 — finalization + reference manifest + PR ready

13.1. Author `.vault/reference/2026-04-27-modelo-100-rule-delta-reference.md`
      — comprehensive per-anexo per-año per-CCAA manifest mirroring
      sibling Tier-L rule-delta references.
13.2. Update `docs/coverage/modelos.md` M100 row to ✅ in every applicable
      column with provenance line citing this PR's commit SHA.
13.3. Author `docs/m100-architecture.md` — architecture map (anexos ×
      régimenes × CCAA × año tensor visualisation, sub-package layout
      diagram).
13.4. Final aggregate exec summary
      `.vault/exec/2026-04-27-modelo-100-renta-full-calc/2026-04-27-modelo-100-renta-full-calc-summary-exec.md`.
13.5. Final verification: `just lint && just typecheck && just test &&
      just hooks` green; `aeat audit rulesets citations` 100%
      aggregate; mutation kill-rate ≥ 90% on M100 surface; coverage
      floor 60% preserved.
13.6. Flip PR draft → ready. Update PR title and body with final
      casilla inventory + per-año BOE source list + per-CCAA deduction
      table summary + multi-agent review sign-offs + per-wave exec
      record links + any `citation-pending` follow-up issues + explicit
      OUT-OF-SCOPE list.
13.7. Body trailer: `Closes #317` + `Closes #341` + `Closes #342` +
      `Closes #343` + `Closes #344`.

## Parallelization

Within a wave, anexo files can be authored in parallel by separate
sessions if needed (independent files). Cross-wave parallelism is
limited because later anexos depend on earlier anexos' casillas
(Anexo G's cuota líquida computation references Anexo F's base
liquidable). Practical sequencing: Waves 5 → 6 → 7 → 8 → 9 → 10 → 11 →
12 → 13, one wave at a time per session.

Within Anexo Ñ (Wave 10), the 15 CCAAs are independent — could be
delegated to parallel subagents if a future session has the budget.
Default: serial authoring with rolling audit between CCAAs.

## Verification

The mission succeeds when **all** of the following are true:

1. **Per-anexo per-año ruleset coverage** — every BOE-printed
   `computed=True` casilla on the M100 template is encoded as a
   `FormulaDefinition`. Inventory enumerated in the rule-delta
   reference manifest. Any `computed=False` casilla justified.
2. **Per-año tarifa, mínimos, art. 20 reducción, RIRPF art. 30 cap,
   LIS amortización tabla, LIS art. 17 inventario method enum** all
   encoded with BOE-anchored citations and stable across 2024 / 2025 /
   2026 (or year-delta documented).
3. **2026 conservative inheritance** — citations for inherited values
   carry `&p=20260228&tn=1` consult-date pin and explicit
   "valor heredado de 2025 al no haberse publicado modificación BOE
   para ejercicio 2026" annotation.
4. **Per-CCAA tarifa autonómica** for Madrid + Cataluña + Andalucía +
   Comunitat Valenciana + Castilla y León encoded; remaining CCAAs
   default tarifa documented.
5. **Per-CCAA per-año deduction inventory** — 15 CCAAs × 3 años with
   all per-deduction casillas + formulas + citations to AEAT manual
   práctico per CCAA.
6. **Ceuta + Melilla 60% reducción** (NOT 50%) encoded at state level
   per LIRPF art. 68.4 post Ley 6/2018.
7. **Multi-anexo borrador extractor** for 2024 / 2025 / 2026 working;
   round-trip closes against synthetic generator.
8. **L1 anchor** target ≥ 5 Renta-Web-Open PDFs per año (manual step;
   waiver acceptable).
9. **Kent integration test** class extended with per-año parametrize
   cases; markers per the brief.
10. **`aeat audit rulesets citations`** 100% on M100 (every año + the
    existing summary).
11. **Mutation kill-rate** ≥ 90% on every M100 newly-added node
    (per-wave audit).
12. **Multi-agent review** sign-offs from gemini-code-assist + codex
    review subagent + claude review subagent documented in PR body.
13. **`just lint && just typecheck && just test && just hooks`**
    green on Windows.
14. **Coverage floor 60%** on `src/aeat` preserved via `just test-cov`.
15. **`docs/coverage/modelos.md`** M100 row flipped to ✅ with provenance.
16. **PR body** cites parent EPIC `#316`, sibling Tier-L refs, ADR,
    research, plan, per-anexo casilla inventory, per-año BOE source
    list, per-CCAA table summary, sign-offs, exec record links,
    follow-up issues, out-of-scope list.
17. **Closes** trailer references all 5 issues: `#317 #341 #342 #343
    #344`.

**Honest limitations to declare in PR body:**

- L1 anchor PDFs require a manual Renta Web Open step; if not landed in
  this PR, waiver per the M123 precedent.
- Per-CCAA 2026 values for 14 of 15 CCAAs are inherited from 2025
  pending each CCAA's 2026 Ley publication. Follow-up issues opened
  per-CCAA refresh.
- Pre-2020 RENTA template support out of scope (XFA limitation).
- Tests verify code correctness, NOT tax-correctness against real Kent
  filings — verification of legal accuracy depends on the BOE citation
  trail + multi-agent review.

## Plan self-review (Wave 4 — runs immediately after this plan lands)

The plan self-review checks the plan against:

- **CLAUDE.md mandates** — pydantic v2 universal, no mocks, marker
  module-level, conventional commits, no wave/phase in code,
  trilingual labels, `aeat.core.errors.AeatError` inheritance,
  `aeat.core.logging.get_logger`, src/aeat/ layout. **PLAN STATUS: covered.**
- **ADR architectural decisions D1-D13** — sub-package layout, per-CCAA
  aggregate casillas, Pydantic amortización + inventario, three Anexo
  D régimen sub-modules, per-año re-author, borrador dispatch
  preserved, L1 anchor strategy, integration test marker, cent-exact
  rounding, multi-agent review per wave, rolling audit, multi-session
  pacing. **PLAN STATUS: every ADR decision mapped to a wave step.**
- **Sibling Tier-L precedents** — module shape, casilla discipline,
  formula DSL idioms, citation discipline, test pattern, mutation
  harness registration, registry pattern. **PLAN STATUS: matched.**
- **No-mocks discipline** — every test uses real Pydantic instances /
  real synthetic PDFs / real CLI invocation. **PLAN STATUS: covered.**
- **Scope-unbounded mandate** — the plan covers the full universe (9
  anexos × 3 régimenes × 15 CCAA × Ceuta/Melilla × 3 años + inventario
  + amortización + tarifa estatal + tarifa autonómica). **PLAN STATUS:
  covered.**
- **Multi-agent review mandate** — gemini auto + codex subagent +
  claude subagent triggered after waves 7, 9, 10, 12. **PLAN STATUS:
  covered.**
- **Rolling audit mandate** — per-wave checkpoint required before
  next wave. **PLAN STATUS: covered.**
- **No-wave-phase-in-code mandate** — wave numbering appears in this
  plan + commit messages + exec records ONLY; never in source code or
  docstrings. **PLAN STATUS: explicit reminder per-wave; compliance is
  an authoring discipline, not a structural constraint.**

**Verdict:** Plan is consistent with all mandates and the ADR's
architectural decisions. Proceed to Wave 5 implementation.
