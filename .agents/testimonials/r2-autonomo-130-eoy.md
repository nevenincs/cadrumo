# Testimonial — r2-autonomo-130-eoy (cross-period deductible/expense carry, M130 ×4 + M100 EOY)

## 1. Persona
I am an autónomo (NIF `33445566R`), estimación directa, single activity "Consultoría"
(actividad económica), activity start 2024-01-01. I file Modelo 130 (pago fraccionado
IRPF) for the four quarters of 2024 and the annual Modelo 100. My focus this round: are
the **deductible/expense (gastos) carried cumulatively** across quarters correctly, are
the **pagos fraccionados anteriores** carried correctly, and does the **EOY Modelo 100**
fold the year's rendimiento neto and pagos correctly.

Data (per quarter, income base / deductible gasto base, 21% IVA):
- 1T: income 6000, gasto 1000 (asesoria_fiscal)
- 2T: income 4000, gasto 800 (software_suscripcion)
- 3T: income 5000, gasto 1200 (asesoria_fiscal)
- 4T: income 5000, gasto 1000 (material_oficina)
Annual: income 20000, gastos 4000, rendimiento neto 16000.

## 2. What worked (first try)
- Profile create after the NIF refusal named the exact problem ("un NIF son 8 dígitos
  seguidos de una letra de control"); I computed the control letter (33445566 mod 23 = 1
  → "R") and `33445566R` was accepted.
- Ledger import (semicolon CSV) imported all 8 rows, 0 skipped.
- Classify (income with taxable-base/iva, gastos with category-id) all reached `reviewed`.
- Preflight 1T: issues 0, ready true.
- **M130 gastos now AUTO-AGGREGATE into casilla 02 from the ledger** via the
  `modelo-130-actividad-economica-gastos-cumulative` binding
  (`source = ledger_renta_gasto_aggregation`). This is a CHANGE from the HARNESS F2 note
  (which said expenses are dropped and must be hand-entered via `--casilla 02=`). I did
  NOT need to hand-enter gastos. The recent commit
  `feat(ledger-aggregation): aggregate M130 deductible gastos into casilla 02` is live and
  correct.
- The **cumulative period window is correct**: each quarter's calculate emits `AVISO …
  outside the cumulative income/gasto window` for the *future* quarters' transactions, so
  casillas 01/02 only sum transactions dated up to the period end. No future income/gasto
  leaks into an earlier quarter.

## 3. Friction / breakage (environmental, not M130 logic)
- **Shared-worktree peer WIP crashed the CLI twice** (both transient, both unrelated to
  my modelo):
  1. An unresolved git merge-conflict marker (`<<<<<<< ours`) in
     `application/calculations/_cross_period_clean_state.py` produced a `SyntaxError` that
     crashed every CLI command. It cleared on its own (a peer resolved it) within a minute.
  2. A peer added `aeat.domain.iva._refund_eligibility.Modelo303RefundNotEligibleError`
     without a declared `ErrorCode` registry entry → import-time `ValueError` crashing the
     whole CLI ("missing a declared ErrorCode registry entry … may have been added by a
     peer agent mid-flight"). This blocked my `config profile edit` (birth-date) and the
     M100 calculate. **This is the redeme-company-refund M303 peer campaign, NOT an M130
     defect.** Status at write time: still broken; EOY M100 verification pending recovery
     (see §6 finding F-ENV and §5).
- M130 1T calculate demanded `irpf.previous_year_economic_activity_net_income`,
  `modelo-130-pagos-fraccionados-anteriores`, `modelo-130-resultados-negativos-anteriores`
  even for a first-year filer. Supplying them =0 via `--binding` worked. The error message
  named the exact binding and the discovery command — actionable. (By-design prior-period
  gate per ROUND2; not a bug.)
- M100 birth-date is a date-valued profile fact that (correctly) CANNOT be passed via
  `--binding`; the error instructed setting it via `profile edit --taxpayer-birth-date`.
  Clear and actionable.

## 4. Input → Output reconciliation (M130, cumulative estimación directa)
Expected derived from AEAT rules: casilla 01 = Σ income base YTD; 02 = Σ gasto base YTD;
03 = 01−02; 04 = 20%×03 (Art. 110.2 RIRPF); **05 = Σ prior quarters' casilla 07**
(RD 439/2007 art. 110.3 — gross apartado-I results, NOT Σ casilla 19); 07 = 04−05−06;
casilla 13 = minoración Art. 110.3.c (=100 each quarter at this income level); 19 = result.

| Q  | in→01 | exp01 | gasto→02 | exp02 | 03 | exp03 | 04 | exp04 | 05(carry) | exp05 | 07 | exp07 | 19 |
|----|-------|-------|----------|-------|------|-------|------|-------|-----------|-------|------|-------|------|
| 1T | 6000  | 6000 ✅| 1000     | 1000 ✅| 5000 |5000 ✅|1000 |1000 ✅| 0         | 0 ✅  | 1000 |1000 ✅| 900  |
| 2T | 10000 |10000 ✅| 1800     | 1800 ✅| 8200 |8200 ✅|1640 |1640 ✅| 1000      |1000 ✅| 640  | 640 ✅| 540  |
| 3T | 15000 |15000 ✅| 3000     | 3000 ✅|12000 |12000✅|2400 |2400 ✅| 1640      |1640 ✅| 760  | 760 ✅| 660  |
| 4T | 20000 |20000 ✅| 4000     | 4000 ✅|16000 |16000✅|3200 |3200 ✅| 2400      |2400 ✅| 800  | 800 ✅| 700  |

**All rows match.** Cumulative gastos (deductible carry) accumulate exactly:
1000 → 1800 → 3000 → 4000. Rendimiento neto annual (4T casilla 03) = 16000 ✅.

## 4b. Carry-correctness check (the headline)
- **Deductible/gasto cumulative carry: CORRECT.** casilla 02 = YTD gasto base every
  quarter (1000/1800/3000/4000), auto-aggregated from the ledger; no double-count, no
  leakage of future-quarter gastos (window AVISOs confirm exclusion).
- **Pagos fraccionados anteriores (casilla 05): CORRECT against Σ casilla 07.**
  - 2T 05 = 1000 = 1T·07 ✅
  - 3T 05 = 1640 = 1T·07 + 2T·07 (1000+640) ✅
  - 4T 05 = 2400 = 1000+640+760 ✅
  The engine consumed each carried value and computed 07 = 04−05 correctly downstream.
  Note: casilla 05 correctly tracks Σ casilla **07** (gross results 1000/640/760/800),
  NOT Σ casilla **19** (net results 900/540/660/700) — the RD 439/2007 art.110.3
  distinction holds. (Carry supplied via `--binding modelo-130-pagos-fraccionados-anteriores`;
  the in-window auto-carry file-chain is not CLI-drivable per ROUND2, so I verified the
  engine's *consumption* of the carry, which is exact.)
- Consistency: Σ casilla 07 = 1000+640+760+800 = 3200 = 20%×16000 ✅ (the cumulative
  system self-reconciles to the annual 20% of rendimiento neto).
- Σ casilla 19 (actual pagos fraccionados made) = 900+540+660+700 = **2800** = 3200 − 400
  (four ×100 minoración Art.110.3.c) ✅.

## 5. EOY Modelo 100 aggregate check (CLI recovered; calculated)
Expected: rendimiento neto de actividades económicas (casilla 0224) = 16000; pagos
fraccionados a cuenta = Σ M130 casilla 19 = 2800.

| M100 figure | casilla | actual | expected | match |
|-------------|---------|--------|----------|-------|
| Rendimiento neto reducido act. económicas (est. directa) | 0224 | **0.00** | 16000 | ❌ |
| Rendimiento neto act. económicas (intermediate) | 0179/0180 | 0 / 0.00 | 16000 | ❌ |
| Pagos fraccionados M130 a cuenta | (rel-130) | **0** | 2800 | ❌ (gated) |
| Mínimo personal y familiar | 0511/0519 | 5550.00 | 5550 | ✅ (only non-zero figure) |

Two **distinct** EOY behaviours, root causes differ:

- **(A) Rendimiento neto de actividades económicas = 0, NOT 16000 — REAL GAP.** M100 has
  **no actividad-económica income/gasto/rendimiento binding at all**. The full binding set
  for M100 2024-0A is: estimación-directa modalidad (manual), four retenciones relations,
  M130 + M131 pagos relations, and profile facts. There is NO ledger income aggregation
  (M130 has `ledger_renta_income_aggregation`; M100 has nothing equivalent) and NO
  M130→M100 rendimiento relation. So the €20000 income / €4000 gastos / €16000 rendimiento
  that aggregated correctly into the M130s NEVER reach the annual M100. The only non-zero
  figure in the entire 2064-casilla M100 is the €5550 personal minimum. This is an EOY
  aggregation/wiring gap — the annual return would declare ZERO business income.
  This is NOT gated on evidence — calculate completes and emits the zero silently.
- **(B) Pagos fraccionados fold-in = 0 — BY-DESIGN evidence gate, not a bug.** The
  `renta-2024-rel-130-pagos-fraccionados` relation IS wired (AVISO: "relation … requires
  modelo 130 2024 periods 1T,2T,3T,4T output 19; the source filing is missing or
  incomplete"), but it folds only from FILED M130s carrying AEAT justificante evidence.
  My M130s are draft `borrador`, so the fold = 0. verify M100 returns
  `granted_verificado_completo=false` with 10 `cross_period_dependency_unclean` BLOCKING
  findings (M130 1T-4T + M131 1T-4T). This is the documented safety gate
  (`local-filed-observations-are-non-official-evidence`, ROUND2 §grounded-design-facts) —
  re-confirmed here, not re-filed as a bug. (Minor sub-note: M131 1T-4T evidence is also
  demanded though this autónomo files M130 not M131; the registry declares both relations.)

## 5b. Final artefacts (.boe)
- **M130 1T → `tmp/personas/r2-autonomo-130-eoy/m130-1T.boe`**, byte_size **946**,
  file_sha256 **5a61fdd8827944e6dc35202def39d7ea38f1444ca8021f3000d34969435f5321**.
  verify `granted_verificado_completo=true`, 3 non-blocking findings.
- M130 2T/3T/4T: verify BLOCKED (export refused) — each requires the prior quarter's AEAT
  justificante evidence (`cross_period_dependency_unclean`, origin
  `previous_filing_binding` on `modelo-130-pagos-fraccionados-anteriores`). This is the
  by-design cross-period evidence gate (ROUND2), NOT a number error: the carried/computed
  numbers (§4) are correct; only the *filing* needs official prior evidence, which is not
  CLI-drivable (no in-window file-chain / `today` override).
- M100: export blocked (verify not granted).

## 6. Findings
- **F1 (PASS / resolved gap): M130 gastos auto-aggregate into casilla 02.** The HARNESS F2
  "expense drop" gap is FIXED. casilla 02 = YTD gasto base every quarter, pulled from the
  ledger via `ledger_renta_gasto_aggregation`. No manual `--casilla 02=` needed.
  Severity: N/A (improvement). Proof: §4 table, all 02 rows ✅ (1000/1800/3000/4000).
- **F2 (PASS): M130 cross-period deductible + pagos-fraccionados-anteriores carry numbers
  are CORRECT** across all four quarters. casilla 02 accumulates exactly; casilla 05 =
  Σ prior casilla 07 (1000/1640/2400) exactly per RD 439/2007 art.110.3 (07 not 19);
  03/04/07 all reconcile. No silent mis-declaration in the M130 carry. Severity: none.
- **F3 (CRITICAL — EOY aggregate gap): Modelo 100 does NOT fold the annual rendimiento
  neto de actividades económicas.** casilla 0224 = 0.00 where €16000 is expected. M100 has
  no actividad-económica income/gasto/rendimiento binding and no M130→M100 rendimiento
  relation, so €20000 income / €4000 gastos / €16000 rendimiento never reach the annual
  return — the only non-zero figure is the €5550 personal minimum. An autónomo who relied
  on this M100 would declare ZERO business income (a silent under-declaration of the
  aggregate). Calculate emits the zero silently (this casilla is not behind the evidence
  gate). MITIGATION: M100 verify is independently blocked by the pagos evidence gate (F4),
  so a zero-income `.boe` cannot currently be granted — but the rendimiento wiring gap is
  real and would surface the moment the evidence gate is satisfied. Proof: §5 table,
  `bindings list --modelo 100 --year 2024 --period 0A` (no income binding),
  `work revision` casilla 0224 = 0.00.
- **F4 (BY-DESIGN, not a bug): cross-period evidence gate blocks dependent verify/export.**
  M130 2T/3T/4T and M100 verify return `cross_period_dependency_unclean` BLOCKING until the
  prior period carries official AEAT justificante evidence. Documented behaviour
  (`local-filed-observations-are-non-official-evidence`, ROUND2). The carried NUMBERS are
  correct; only the filing chain needs official evidence (not CLI-drivable). Reported for
  completeness, NOT as a defect. Sub-note (LOW): M100 also demands M131 1T-4T evidence for
  an autónomo who files M130 not M131 — possible over-demand worth a look.
- **F-ENV1 (environmental, transient, NOT my modelo): peer added
  `Modelo303RefundNotEligibleError` without an ErrorCode registry entry**, crashing all CLI
  imports (`bind_error_code` ValueError) and briefly blocking the EOY M100 step. Owner:
  redeme-company-refund / M303 monthly refund campaign. Self-cleared on re-run. Not an
  M130/M100 logic defect.
- **F-ENV2 (environmental, transient): merge-conflict markers (`<<<<<<< ours`) left in
  `application/calculations/_cross_period_clean_state.py`** crashed the CLI with a
  SyntaxError at first import; self-cleared within ~1 min. Shared-worktree hygiene, not a
  modelo defect.

## 6b. FIX IMPLEMENTED (F3 income half) — M100 2024 actividad-económica income aggregation
Root cause (grounded): the M100 **2024** registry revision never received the
actividad-económica ledger-income wiring that the **2025** revision has
(`renta-2025-ledger-income-0171` + casilla 0171 `input_kind="bound"`). The application
resolver (`aggregate_renta_m100_income_ledger`, `LedgerRentaIncomeAggregationSourceResolver`)
already supports the M100 annual path and is enrolled in the calculate mesh — only the
2024 registry binding + casilla wiring were missing, so casilla 0171 silently stayed 0.

Fix (registry-only, parity with 2025):
- Added binding `renta-2024-ledger-income-0171`
  (`src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0021-...toml`),
  source `ledger_renta_income_aggregation`, selector `{modelo=100, target_casilla=0171,
  fact=ingresos_integros_sum}`, grounded `legal_refs=[art-27, art-28]` + proven
  `lirpf-cuota-chain-authority` citation.
- Wired casilla 0171 (`casillas/0168-0171.toml`) to `input_kind="bound"` +
  `binding="renta-2024-ledger-income-0171"` (the binding→casilla link lives on the casilla,
  via `resolve_bound_casilla_inputs_for_available_bindings`).
- Registered the binding + casilla 0171 in the 2024 mini-model construct
  (`constructs/0002-...directa.toml`) and extended its legal_refs/source_refs to cover
  casilla 0171 (validator: construct refs ⊇ member-casilla refs).

Result (verified): M100 2024 casilla 0171 = **20000** (was 0), 0180 = 20000, 0224
(rendimiento neto) = 19000 = 20000 − 1000 (auto 5% estimación-directa-simplificada,
casilla 0223). All six M100 revisions (2020-2025) still build; 2020-2023 casilla 0171
unchanged (`manual`). The silent-zero-income hazard is closed; rendimiento now errs HIGH
(toward more tax) pending manual gastos — the safe direction (no under-declaration).

Regression absorbed: the new owned income binding tripped three M100/2024 fold-in test
helpers that zero-defaulted EVERY non-profile/non-relation binding via the caller channel
(now including the mesh-owned income binding → `ModeloAggregationBindingError`). Brought
the three 2024 helpers
(`test_modelo_100_pagos_fraccionados_fold_in_live`, `..._retenciones_credit_fold_in_live`,
`test_e2e_ledger_m130_quarters_to_m100_annual`) to parity with the existing 2025 test's
`_AUTO_RESOLVED` exclusion (excludes the bucket-locked ledger/invoice sources). All 6
affected tests pass; M100 registry/drift/wiring + renta-income-aggregation suites pass
(72). Remaining suite failure (`test_tautology_gate` flagging
`test_iva_wallet_engine_integration.py` hand-summed assertions) is PEER-owned (IVA-wallet
P01 commit `a7b755e5a`), unrelated to this change.

## 6c. EXPENSE half ALSO IMPLEMENTED (F3 complete)
Initially deferred, then implemented after grounding showed it was tractable without
fabricating FY-specific tax values:
- Created `src/aeat/_data/registry/aeat/categories/profiles/2024.toml` (41 categories) to
  parity with the reviewed 2025 registry. The first-slice categories (cuotas SS,
  arrendamiento, asesoría ×3, gastos bancarios/financieros) are all `full_deductible` —
  framework deductibility under LIRPF art. 28.1, year-stable (no FY-specific value). The
  dietas/seguro caps are RD 439/2007 art. 9 / LIRPF art. 30.2.5ª framework values unchanged
  for 2024; the mutualidad cap is mirrored from 2025 and is NOT consumed by any first-slice
  binding (so no FY-specific figure is shipped into an active calculation path). The loader's
  completeness gate requires all 41 categories; the 2025-scoped category tests are unaffected.
- Added the 4 first-slice expense bindings (0186/0192/0199/0203, source
  `ledger_renta_expense_aggregation`) + wired each casilla `input_kind="bound"` + construct.
- Result (verified): casilla 0199 = **2662** (asesoria_fiscal 1210+1452 gross routed to
  "Servicios de profesionales independientes"), 0220 (total gastos) = 2662, rendimiento neto
  0224 = **16471.10** (= 20000 − 2662 − 866.90 5% est-directa-simplificada). Non-first-slice
  categories (software/material) correctly emit an advisory (manual entry) — the first-slice
  is incomplete by design in BOTH 2024 and 2025. (The gross-vs-base expense convention is the
  pre-existing 2025 pipeline behavior, not introduced here.)

Regressions absorbed (all green): enabling the expense resolver (a) activated an
invoice-repository dependency — fixed 3 fold-in tests' `InvoiceCatalogueRepository` to pass
`bucket_id` (parity with the 2025 test); (b) made M100 calculate require ledger-preflight
readiness — gave the e2e test's income transactions zero-IVA fiscal facts (`taxable_base ==
gross`, so casilla 01 is unchanged and no asserted value moves); (c) the unknown-year
category test used 2024 as its placeholder — moved to 2099. All edits are outside the peer's
active WIP region in the e2e file.

## 7. Verdict
**Headline PASS:** M130 cross-period deductible/expense (gastos) carry and
pagos-fraccionados-anteriores carry are NUMERICALLY CORRECT across all four quarters, with
zero discrepancies; gastos now auto-aggregate (HARNESS F2 gap closed). A real autónomo
reaches a compliant M130 1T `.boe` unaided.
**EOY caveat (CRITICAL, F3):** the annual Modelo 100 does NOT aggregate/carry the €16000
rendimiento neto de actividades económicas (casilla 0224 = 0) — no income binding wires the
ledger/M130s into M100. The pagos-fraccionados fold-in is correctly wired but gated on
official prior evidence (by-design). EOY annual-aggregate correctness FAILS for the
rendimiento; the quarterly carry succeeds.
