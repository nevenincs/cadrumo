# Edge-case QA: CALCULATION / MODELO probing (adversarial)

Persona env: `/tmp/edge-calc`; profile `edgecalc` (natural_person, actividad_economica, activity-start 2024-01-01).
Method: real CLI; arithmetic cross-checked against AEAT identities, not the registry formula.

---

## FINDING 1 — Uncategorised business expense SILENTLY dropped while income with the same tag IS counted (BUG, HIGH)

- Setup: `ledger add ... --amount 1000 --direction INCOMING --irpf-category actividad_economica`
  and `ledger add ... --amount 5000 --direction OUTGOING --irpf-category actividad_economica`
  (expense given the SAME `--irpf-category actividad_economica`, no `--classification`).
- Command: `aeat app modelo work calculate --modelo 130 --year 2024 --period 1T --binding irpf.previous_year_economic_activity_net_income=0`
- Expected (arithmetic): casilla 01 (Ingresos)=1000, casilla 02 (Gastos)=5000, casilla 03 (rendimiento neto)=1000-5000 = -4000.
- Actual: `casilla 01 = 1000`, **`casilla 02 = 0`**, `casilla 03 = 1000.00`, casilla 04 pago fraccionado = 200.00, casilla 19 = 100.00 (a POSITIVE result to pay).
- Root cause: income aggregation honours `irpf_category=actividad_economica` as the authoritative eligibility gate
  (`_renta_income_ledger.py:_income_business_amount`), but gasto aggregation gates ONLY on
  `business_classification` BUSINESS/MIXED and the docstring states "PERSONAL / unclassified OUTGOING rows are skipped
  silently ... never produce an issue" (`_renta_gasto_ledger.py:65`). So the identical `--irpf-category` tag counts an
  income but not a parallel expense, with ZERO advisory/notice on the calculate output (text and would-be JSON `notices: []`).
- Impact: an operator who tags both legs `actividad_economica` (a natural symmetric workflow) silently OVER-declares —
  a €5000 deductible gasto vanishes and a loss return becomes a €200 payment, with no warning. This is a silent wrong
  figure. (Once the expense is `ledger classify <id> --classification BUSINESS`, casilla 02=5000 and 03=-4000 correctly.)
- Verdict: BUG. Severity HIGH (silent wrong figure / asymmetric eligibility gate, no operator-facing advisory).

## FINDING 2 — 130 LOSS handled CORRECTLY (verified against AEAT, NOT a bug)

- Setup: expense classified BUSINESS so casilla 02 picks it up; income 1000, expense 5000.
- Command: `calculate --modelo 130 --year 2024 --period 1T`.
- Actual: casilla 03 = -4000.00 (loss), casilla 04 pago fraccionado = 0.00, casilla 13 minoración = 100, casilla 19 = -100,
  saldo-negativo-fin-periodo = 100.00 carried forward; `verify` grants `verificado_completo=true` (advisory only).
- Cross-check: AEAT M130 instructions — casilla 14 = casilla 12 - casilla 13, NO cap on casilla 13 itself (the cap is on
  casilla 16). The €100 minoración (prev-year net income <= 9000) applies as a fixed amount even on a zero/negative
  quarter; the negative result is legitimate and carries to saldo negativo. Confirmed via official sede.agenciatributaria.gob.es
  M130 instrucciones + corroborating sources.
- Verdict: CORRECT behaviour. The verify gate does NOT falsely grant on a loss — a loss return is legitimately complete.

## FINDING 3 — 130 cumulative 1T->2T figures CORRECT

- Setup: Q1 income 1000 / expense 5000; Q2 income 3000 / expense 500 (all BUSINESS-classified, actividad_economica).
- Command: `calculate --modelo 130 --year 2024 --period 2T --binding irpf.previous_year_economic_activity_net_income=0
  --binding modelo-130-pagos-fraccionados-anteriores=0 --binding modelo-130-resultados-negativos-anteriores=100`.
- Expected (arithmetic, YTD cumulative): casilla 01 = 1000+3000 = 4000, casilla 02 = 5000+500 = 5500,
  casilla 03 = 4000-5500 = -1500; prior-quarter loss (-100 saldo) feeds casilla 15.
- Actual: casilla 01=4000, casilla 02=5500, casilla 03=-1500.00, casilla 17=-200.00 (casilla14 -100 minus casilla15 100),
  casilla 19=-200.00. Cumulative window correct.
- Verdict: CORRECT.

## FINDING 4 — 303 purchases-only (credit) -> compensación CORRECT

- Setup: only one IVA purchase (taxable_base 1000, IVA 210, domestic_general_21, BUSINESS, category material_oficina); no sales.
- Command: `calculate --modelo 303 --year 2024 --period 3T`.
- Expected: cuota devengada=0, deducible=210, resultado=-210, no mid-year refund -> carry as compensación 210.
- Actual: iva.cuota-devengada-total=0.00, iva.cuota-deducible-total=210.00, iva.resultado-regimen-general=-210.00,
  casilla 64/66/71=-210.00, iva.compensacion-generada-periodo=210.00, iva.compensacion-disponible-fin-periodo=210.00.
- Verdict: CORRECT. Negative IVA result correctly becomes a carry-forward compensación.

## FINDING 5 — 303 idempotence CORRECT

- Command: `calculate --modelo 303 --year 2024 --period 3T` run twice.
- Actual: byte-identical key figures both runs; `work revisions` shows revision_count=1 (recalc REPLACES the draft, no duplicate
  accumulation; content-addressed revision id stable).
- Verdict: CORRECT (idempotent).

## FINDING 6 — Boundary period tokens (0A vs 4T) CORRECT

- 130 0A -> rejected ("no revision for year=2024 period='0A'"); 303 0A -> rejected; 390 4T -> rejected; 390 0A -> accepted.
- Verdict: CORRECT. Periodicity boundary enforced (quarterly models reject annual token and vice-versa). Error names the offending token.
- Minor: rejection message is generic ("no revision for ... period=...") rather than listing the accepted period set for that modelo.

## FINDING 7 — 303 exempt/zero-rated -> NO false unrouted-IVA advisory CORRECT

- Setup: isolated `domestic_exempt` sale (base 2000, IVA 0) as sole valid 4T transaction.
- Actual: cuota devengada=0, deducible=0, resultado=0; the exempt sale does NOT trigger the "unrouted declarable IVA" advisory
  (matches rule ledger-iva-advisory-only-on-cuota-bearing-categories). Out-of-period transactions from other quarters DO emit
  "transaction date ... outside 2024 4T ... not declared on this filing" advisories (legitimate no-silent surfacing; noisy but correct).
- Verdict: CORRECT (exempt exclusion works). LOW note: out-of-period advisory volume is high.

## FINDING 8 — no-silent-under-declaration on M131 (positive rendimiento, zero pago) -> ADVISORY fires CORRECT

- Setup: `calculate --modelo 131 --year 2024 --period 1T --casilla 01=10000` (positive rendimiento), casilla 02 pago left 0.
- Actual: chain resolves to casilla 13/15 = 0 (zero pago fraccionado on positive activity). `verify` grants
  verificado_completo=true BUT with finding_count=1 ADVISORY: "Los rendimientos netos ... (C01) son positivos pero el pago
  fraccionado ... (C02) es cero; revise la casilla 02 ... (minimo 2 por 100)" (legal_refs rd-439-2007:art-110).
- Verdict: CORRECT. Positive-input/zero-result surfaces a non-blocking advisory, not a silent grant (rule satisfied).

## FINDING 9 — Unrendered `%{detail}` placeholder in calc-blocking preflight message (BUG, MEDIUM)

- Command: `calculate --modelo 303 ...` with an OUTGOING expense missing category/classification.
- Actual: "Error. ledger preflight blocks modelo calculation: transaction <id> missing_business_classification: **%{detail}**.
  Run `aeat app ledger preflight ...`" -- the `%{detail}` template variable leaks raw (verified in both es and en runs).
- Root: locale `ledger_*_blocked: '... %{transaction_id} %{reason}: %{detail}. ...'` (src/aeat/locales/es.yml) -- the calc-path
  caller substitutes transaction_id + reason but NOT detail, so the operator never sees WHY (the real detail
  "deductible-expense ledger transaction has no category_id" only appears via `ledger preflight`, not in the blocking message).
- Verdict: BUG. Severity MEDIUM (degraded diagnostic; the actionable reason is dropped from the operator-facing block message).

## FINDING 10 — amend/complementaria flow correctly gated (NOT a bug)

- `amend --from-filing-record nonexistent` -> "No existe ninguna declaración registrada con id=..."; missing `--set`/`--reason`
  correctly refused; invalid `--kind banana` -> "--kind debe ser uno de 'complementaria', 'sustitutiva'; se recibió banana"
  (instructive, lists accepted set). Amend requires an official AEAT-imported filing record (justificante/CSV/live capture) --
  cannot be driven without real evidence (correct per aeat-safety-legal-gates).
- Minor: `--kind` is bare TEXT (late refusal) rather than a click Choice; acceptable per architecture rule (refusal lists the set).
- Verdict: CORRECT (conservative gating).

## FINDING 11 — recargo/late-filing bands: NOT computed (acceptable, by design)

- `overview backlog` correctly lists overdue obligations with closing dates (late_count=8). There is no recargo (LGT art. 27)
  surcharge calculation surface -- consistent with the never-file-live posture (recargo accrues at AEAT filing, outside the app).
- Verdict: ACCEPTABLE. No claim of recargo computation; no silent wrong figure.

## CROSS-CUTTING NOTE (reinforces FINDING 1)

- The income transaction a615318a (irpf_category=actividad_economica, business_classification=NOT_YET_PROCESSED) fed M130
  casilla 01=1000 SILENTLY, yet 303 preflight on the same row flags `missing_business_classification: NOT_YET_PROCESSED ...
  is not ready for modelo calculation`. The M130 income gate bypasses the classification that the IVA preflight enforces --
  an unreviewed (NOT_YET_PROCESSED) row was consumed into an IRPF figure with no preflight gate. Asymmetric readiness contract.
