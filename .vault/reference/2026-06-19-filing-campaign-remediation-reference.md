---
tags:
  - '#reference'
  - '#filing-campaign-remediation'
date: '2026-06-19'
modified: '2026-10-03'
body_hash: 'sha256:7176d732b4c968de49f629b9c3c797473cb56e420de398c1dcb376af98059a73'
related: []
---

# `filing-campaign-remediation` reference: `Filing-campaign findings: RAG-grounded fix-site inventory`

RAG-grounded (`uv run --no-sync vaultspec-rag search ... --type code`) fix-site inventory for every issue the filing-persona campaign surfaced, verified at HEAD `7208bb3f0`. Each finding names the canonical site(s) to change and the test surface to extend. C0 (the cross-period deadlock) has its own decision record; this reference grounds the remaining findings (C1 to C4, H1 to H3, M1 to M4) so a coder can act without re-discovery. Severity and symptoms are summarised from the coordinator findings and the per-persona testimonials.

## C0 — Cross-period observation deadlock (CRITICAL)

Decided in the companion ADR. Tests: `test_local_cross_period_carry.py`, `test_e2e_ledger_m130_quarters_to_m100_annual.py`, `test_e2e_ledger_m303_quarters_to_m390_annual.py`.

## C1 — Modelo 303 un-exportable: no operator-settable jurisdiction_scope (CRITICAL)

Absent gives casilla 65 = 0, casilla 71 = 0 (silent-zero), `DRAFT_HAS_ERRORS`. No `profile create` / `edit` flag and no wizard step writes it.

- **Grounding:** consumer `_profile_binding.py:232`; tests `test_state_attribution_ratio.py`, `test_bucket_aggregation_flow.py:361`. Confirmed by gestor, autonomo-iva-303, iva-crossperiod-303 testimonials.

## C2 — Modelo 303 prorrata-porcentaje formula-divergence blocks every ordinary 303 (CRITICAL)

With both prorrata volumes = 0 (the ordinary full-deduction case) the percentage formula short-circuits on the 0/0 denominator and emits a `formula_trace` carrying only `(iva.prorrata-volumen-total,)`; the draft validator set-equality check (`set(trace) == set(formula_inputs)`) raises `formula-divergence`, surfaced opaquely as `DRAFT_HAS_ERRORS`.

- **Grounding:** `test_build_draft_conditional_formula_trace.py`, `domain/iva/tests/test_prorrata.py`. Confirmed autonomo-iva-303, iva-crossperiod-303.

## C3 — Modelo 100 unreachable: no not-applicable path for withholding/instalment deps (CRITICAL)

M100 verify raises about 33 blocking `cross_period_dependency_unclean` demanding justificante evidence for withholding/instalment modelos (111/115/123/130/131/193) an employee never files; `activity-start-date` scopes only the prior YEAR, not same-year relations.

- **Grounding:** `test_cross_period_clean_state.py:834`, `test_cross_period_finding_legal_grounding.py`. Confirmed renta-100-fullyear.

## C4 — Modelo 100 silent drop of the resultado chain (CRITICAL; no-silent-under-declaration)

With income entered but the 130/131 relations unsupplied, casillas 0604/0609/0610/0670 (resultado de la declaracion) are ABSENT from the revision with only a non-blocking AVISO; the relation ids are not listed by `bindings list --missing`.

- **Grounding:** `test_modelo_100_pagos_fraccionados_fold_in_live.py:295/314`, `test_modelo_100_retenciones_credit_fold_in_live.py`. Confirmed renta-100-fullyear. Pairs with H1.

## H1 — No ledger base/expense aggregation into modelo casillas (HIGH; systemic)

M303 leaves taxable bases (07/28) at 0 while populating cuotas (cuota-without-base, AEAT-rejectable); M130 drops deductible expenses from casilla 02; M100 maps no ledger income.

- **Grounding:** `test_ledger_renta_income_binding.py`, `test_ledger_renta_expense_binding.py`, `test_renta_gasto_aggregation.py:314`. Confirmed across IRPF and IVA personas.

## H2 — DRAFT_HAS_ERRORS verify abort surfaces zero findings (HIGH)

`verify` grants completeness, then a post-grant workflow gate rebuilds a submission draft via `build_draft`; a draft ERROR aborts as the opaque `DRAFT_HAS_ERRORS` with no findings list and no persisted report.

- **Grounding:** `test_engine.py:537/564/784`. Confirmed autonomo-iva-303, gestor; once C2 lands this fires far less, but the opaque-abort defect is independent.

## H3 — Modelo 200 cuota integra does not propagate to cuota a ingresar (HIGH)

Hand-entered resultado contable correctly yields base, tipo, cuota integra (18,400 at 23 percent), but DP200014B:00599 (cuota del ejercicio a ingresar) stays 0 — a calculation-chain break.

- **Grounding:** confirmed sociedad-200-is.

## M1 — work dependencies ignores activity-start-date (MEDIUM)

Over-reports blockers verify scopes out: `work dependencies` does not apply the pre-activity suppression that `_cross_period_clean_state.py` (`partition_cross_period_requirements_by_activity_start`, around line 450) and `_verification_actions.py:761` already apply in verify.

- **Fix:** thread `activity_start_date` into the `work dependencies` projection so it mirrors the verify-path suppression. Site: the projection behind `test_modelo_work_ux.py:398`; reuse `partition_cross_period_requirements_by_activity_start`.
- **Grounding:** `test_modelo_work_ux.py:398`, `test_cross_period_clean_state.py:1271/1309/1391`. Confirmed Marco M130 testimonial.

## M2 — Modelo 130 casilla 13 minoracion basis (MEDIUM; grounding)

The minoracion gradation (100/75/50/25/0) gates on `irpf.previous_year_economic_activity_net_income`, yielding a flat 100 for a 20k-euro first-year earner where the cumulative-income reading of art. 110.3.c would give 0 at 3T/4T (cumulative over 12.000).

- **Grounding:** `test_modelo_130_carry_forward_continuity.py:143`. Flagged Marco testimonial finding 6.

## M3 — Date-typed profile bindings unsatisfiable via --binding (MEDIUM)

The `--binding` channel is decimal-only; date-typed profile bindings such as `renta-2024-profile-taxpayer-birth-date` reject both `=0` and a date string. The only path is profile personal data, but `profile create` refuses to overwrite, leaving only the interactive wizard.

- **Grounding:** `test_date_relation_routing.py`, `test_borrador_binding.py:346/421`. Confirmed Marco testimonial finding 5.

## M4 — Mandatory casilla 02 at zero (MEDIUM; UX)

A zero-expense M130 still blocks verify with `missing_required_casilla 02` until `--casilla 02=0` is supplied manually.

- **Grounding:** `test_verificado_completo_regression.py:207`, `test_verification_substance.py:423`. Confirmed Marco testimonial finding 2 (matches harness F2).
