---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-11-01'
modified: '2026-11-01'
body_schema: 'body-v2'
body_hash: 'sha256:82728830d4de8efe29b6bed2c51691692a0573999cca906181fdcd8e749776ca'
related:
  - "[[2026-11-01-export-parity-income-imputation-criterion-research]]"
  - "[[2026-09-27-export-parity-renta-withholding-sources-adr]]"
  - "[[2026-09-23-calendar-obligations-payer-fact-declaration-state-adr]]"
---
# `export-parity` adr: `income imputation criterion` | (**status:** `proposed`)

## Problem Statement

The ledger dates every activity income row and its withholding by bank date (`src/cadrumo/application/aggregation/renta_income_ledger.py:926-940`), and it dates activity expenses the same way (`src/cadrumo/application/aggregation/renta_gasto_ledger.py:488`, `:599`, `:661`; `src/cadrumo/application/aggregation/renta_ledger.py:972`). Bank dating is the cash-basis (cobros y pagos) criterion. In law, the default is accrual (devengo), and cash basis is an election the taxpayer declares in Modelo 100 casilla 0169. That casilla is currently unbound. As a result, for an accrual taxpayer, a December invoice paid in January credits the wrong year in both Modelo 100 casilla 0599 and Modelo 130 casilla 06.

The accepted withholding-sources ADR keeps 0599 advisory until this temporal rule is grounded. `2026-11-01-export-parity-income-imputation-criterion-research` now grounds it. This record decides how Cadrumo represents the taxpayer's criterion, and how income and withholding are keyed under each criterion. It also defines the evidence bar for presenting 0599 for promotion. The operator ruled on 2026-11-01 that the criterion is a typed profile fact.

## Considerations

- Accrual is the legal default, and cash basis is an election available only outside Código de Comercio accounting. The election covers all activities, must be declared in every return, and lasts at least three years (research, "Accrual is the default" and "Cash-basis election").
- The criterion governs income and expense alike. LIS art. 11.1 imputes "ingresos y gastos" to the period of devengo, RIRPF art. 7.1 applies that rule, and the art. 7.2 election is "para imputar temporalmente los ingresos y gastos de todas sus actividades económicas" (research, "Accrual is the default" and "Cash-basis election"). Keying only income by the criterion would leave expenses on cash basis for an accrual taxpayer. In Modelo 130 this is casilla 01 (role `irpf_pf_ingresos`) and casilla 02 (role `irpf_pf_gastos`) (`src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/casillas/0001-declarations.toml:2-17`).
- 0169 is repeated in each estimación directa activity block (`/ActividadEstDirecta`, research, "Cash-basis election"), and the registry models it in the repeating `actividad_est_directa` section (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:1240-1246`). The Modelo 100 credit and criterion work lands at the post-rectification 2022 baseline (plan Step P05.S21).
- Withholding is imputed to the same year as its income. The right to deduct it arises only on payment. When the accrual year was filed before the payment, that year is rectified through an autoliquidación rectificativa for IRPF 2024 and later. The withholding is never credited in the payment year (research, "TEAC unification doctrine"; TEAC 00/03187/2011, DGT V1429-19, V0486-14 and V1177-25).
- Modelo 130 follows the same imputation (DGT V3298-15). Whether withholding paid after the quarter, or remitted on an unpaid invoice, may be deducted in that quarter is not settled in primary text (research, "Modelo 130").
- An invoice with no operation date documents an operation on its issue date (RD 1619/2012 art. 6.1.i). An advance-payment date is not an accrual date (research, "Accrual date").
- The profile schema already treats operator facts as "absent means undeclared" (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:937`). `2026-09-23-calendar-obligations-payer-fact-declaration-state-adr` rejects defaulted answers as silent under-declaration.
- The operator prefers accrual as the default answer.
- `no-silent-under-declaration`, and the rule that absent, unknown, advisory and proven-zero stay distinct (the project's aggregation and completeness invariants).

## Considered options

- **Absent means devengo.** This matches the legal default and costs no question. Rejected: a fresh or imported profile cannot see a cash-basis election made in an earlier return, so the product would silently apply the wrong criterion for up to three years. It also contradicts the schema convention and the payer-fact ruling.
- **Absent means undeclared, with devengo as the proposed answer.** The wizard preselects devengo and the operator confirms it in one step. Until then, only the outputs the criterion can change are held back. Recommended, pending the operator's ruling on what an absent fact means (see "Open questions").
- **A per-activity criterion.** It mirrors the per-activity casilla 0169 element. Rejected: RIRPF art. 7.2.1.º makes the election cover all activities.
- **Refuse to store a criterion change within three years.** Rejected: the profile records what the taxpayer declares, and art. 7.2.2.º forces a change when the election loses effect. A finding states the conflict without falsifying the record.
- **Credit accrued withholding in the accrual year before payment.** Rejected by the TEAC unification criterion.
- **Credit accrued withholding in the payment year.** Rejected by RIRPF art. 79 and the DGT consultas.
- **Include in Modelo 130 casilla 06 by imputation alone, following V3298-15.** Kept only as an advisory alternative pending the operator question. It can over-credit a pago a cuenta against the payment rule.

## Constraints

- `2026-09-27-export-parity-renta-withholding-sources-adr` stays in force:
  - 0599 sums only `DECLARED_ON_LINKED_INVOICE` withholding.
  - Inferred rows stay advisory.
  - Payer-side returns never feed a credit casilla.
  - Every disagreement blocks.

  This record adds the temporal rule that ADR deferred. It proposes one wording change to that ADR, set out under Consequences, and does not apply it.
- The per-binding capability grade being decided under plan Step P01.S01 carries every "advisory" outcome named here. Advisory values never reach an exported file.
- The criterion fact is private financial profile data. It is persisted only through the profile's encrypted custody.
- Every numeric assertion uses an independent, hand-derived oracle (`2026-06-01-calculation-test-oracle-discipline-adr`). Each test runs through the real resolver.
- Binding obligations: everything under Implementation except the items marked as hypotheses.
- Out of scope:
  - Modelo 131.
  - The atribución de rentas entity flag (casilla 1576).
  - Operaciones a plazos.
  - Apportionment of multi-period services.
  - Foral territories.

## Implementation

We will add a typed, effective-dated imputation-criterion profile fact. Ledger activity income, expenses and withholding are keyed by the fact's criterion. Withholding is credited only on payment, and payment after filing becomes a rectification finding. Casillas 0169, 1443 and 1487 are bound from the fact. Work is bounded to plan Steps P05.S21, P05.S22, P05.S30, P05.S31 and P05.S08.

Dependencies needing an operator ruling. The open questions below gate the Steps that implement them (plan Step P01.S27). Keying expenses and the Modelo 130 casillas by the criterion changes Modelo 130 goldens and expense-ledger consumers that other sessions own; plan Step P01.S28 coordinates them before P05.S22 lands, with its scope ruled by the operator. This adds no product scope.

1. **Profile fact (P05.S21).**
   - Key: `activity_income_imputation_criterion` in the `irpf` section.
   - Values: `enum_values = ["devengo", "cobros_y_pagos"]`, `effective_dated = true`, one value per ejercicio, sensitivity `financial`.
   - Model selector: `irpf.activity_income_imputation_criterion`.
   - `legal_refs`: `rd-439-2007:art-7`, `ley-35-2006:art-14` and `ley-27-2014:art-11`.
   - Proposed, pending the operator's ruling: absent means undeclared, never `devengo`. The wizard question preselects `devengo` as the proposed answer and explains when cash basis is open. A non-interactive setup leaves the fact absent; only an interactive answer or an explicit CLI flag writes it.
   - The legal keys use the catalogue's article form. `ley-27-2014:art-11` exists (`src/cadrumo/_data/registry/aeat/legal/is.toml:42`); `rd-439-2007:art-7` and `ley-35-2006:art-14` are added by plan Step P02.S14 under `2026-11-01-export-parity-binding-capability-grade-adr`, and S21 reuses them.
2. **Eligibility companion fact (P05.S21).**
   - Key: `codigo_comercio_accounting`, an optional, effective-dated boolean meaning "obliged to keep, or keeps voluntarily, accounting under the Código de Comercio" (RIRPF arts. 7.2.3.º and 68.2).
   - It is asked only when `cobros_y_pagos` is chosen.
   - `cobros_y_pagos` is admissible for an ejercicio only when `estimation_regime` is declared and `codigo_comercio_accounting` is `false`.
   - Ineligible means `true`, or an undeclared regime or companion. In that case, verify raises a blocking finding that names the provision. Calculation does not fall back to devengo silently.
3. **Three-year minimum (P05.S21).**
   - Enforced as a finding, not a refusal. Verify blocks an ejercicio declared `devengo` when the fact history, or a captured filed Modelo 100 carrying 0169, 1443 or 1487, shows a `cobros_y_pagos` election within the two preceding ejercicios.
   - Exception: the election lost effect under art. 7.2.2.º, shown by `codigo_comercio_accounting = true` in the changed year.
   - A conflict between the profile history and a filed observation also blocks.
   - How the three years are counted, in particular whether the election year is the first of the three, is an open legal reading for the operator. Until it is ruled, verify reports the conflict under the stricter count and names the reading it applied.
4. **Casilla binding (P05.S21, whose write set already names the Modelo 100 registry at the 2022 baseline; serialized with the other Modelo 100 edits).**
   - Bind 0169, 1443 and 1487 at the post-rectification 2022 baseline, inherited forward. No binding is placed at the 2020 or 2021 revisions.
   - 0169 repeats per estimación directa activity block, and 1443 and 1487 per objetiva block. Each is a repeating binding over the same row source that enumerates its block's activities, emitting one row per activity with the one fact value, because the election covers all activities. The row count comes from the block's row source, never from the fact. Where a revision has no producer enumerating a block's activities, the binding cannot be authored and the casilla stays unresolved; whether such a producer exists for each block is a hypothesis to confirm in S21.
   - Each casilla is marked iff the fact is `cobros_y_pagos` and blank iff it is `devengo`.
   - Absent leaves the casilla unresolved, which blocks export rather than writing blank.
   - Add `rd-439-2007:art-7` to the three casillas' `legal_refs`.
5. **Ledger keying (P05.S22).** The rule applies to activity income and activity expenses alike, through the income ledger (`renta_income_ledger.py`) and the expense paths (`renta_gasto_ledger.py`, `renta_ledger.py`), and so to Modelo 130 casillas 01 and 02 and to the Modelo 100 activity blocks.
   - Under `cobros_y_pagos`: income, expenses and withholding are dated by receipt or payment, meaning bank `value_date`, else `booked_date`, as today.
   - Under `devengo`, expenses are dated by accrual on the same rules as income: a received invoice by its `operation_date` when its role is `OPERATION_PERFORMED`, else its `issued_at`. An expense row with no linked document has an unknown accrual date unless its category carries a typed accrual rule, and it is treated like an unlinked receipt below. Which expense categories can carry such a rule is a hypothesis to confirm in S22.
   - Under `devengo`, the population for a window is the issued activity invoices that accrue in it, whether paid or not:
     - Accrual date is `operation_date` when its role is `OPERATION_PERFORMED`, else `issued_at` when no operation date is stated.
     - An invoice whose date role is `ADVANCE_PAYMENT_RECEIVED` has an unresolved accrual and stays advisory.
     - An activity receipt with no linked issued invoice has an unknown accrual date. It is surfaced as advisory and excluded from the filing-grade value.
     - Receipts linked to invoices that accrue in another window serve only as payment evidence for those invoices.
   - When the fact is absent, rows whose year and window are the same under both criteria resolve normally. Any straddling row is unresolved and names the missing fact.
6. **Accrued-but-unpaid withholding (P05.S22).**
   - Under `devengo`, invoice withholding is imputed to the accrual ejercicio. It enters 0599 only when a linked receipt proves payment, whatever the receipt's date.
   - Unpaid withholding is excluded from 0599 and reported as a non-blocking finding with its count and amount.
   - Payment arriving after the accrual year has a local `PRESENTADO` revision raises a rectification finding on that year. The finding names the invoice, the amount, and the autoliquidación rectificativa route. The amount is never credited in the payment year.
   - How a partially paid invoice's withholding is split is an open legal reading for the operator. Until it is ruled, a partially paid invoice's withholding stays advisory.
7. **Modelo 130 (P05.S22).**
   - Casillas 01 (income) and 02 (expenses) follow the criterion within the cumulative window, under item 5.
   - Casilla 06 counts withholding imputed to the window and paid on or before the window end.
   - Withholding imputed to the window but paid later, and withholding remitted on an unpaid invoice, are excluded and surfaced as advisory. Whether either may be deducted in that quarter is an open legal reading for the operator. Exclusion only defers the credit to the annual return.
   - The fourth-quarter cross-check of plan Step P05.S30 therefore compares 0599 against casilla 06 plus the itemised withholding paid after the window end, so a legitimate timing difference does not block.
8. **Change of criterion (P05.S22).**
   - Under RIRPF art. 7.4, rows already imputed in the prior year under devengo are excluded from a first cash-basis year, with a finding.
   - Rows that both criteria would leave uncomputed, on a change from cash to accrual, stay unresolved and block. Which year receives them under art. 7.4 is an open legal reading for the operator.
9. **Promotion of 0599 (P05.S08) and of Modelo 130 casilla 06 (P05.S31).** Each capped binding has its own promotion path under `2026-11-01-export-parity-binding-capability-grade-adr`. A promotion is presented for operator ruling only when this record is accepted and the resolver has the following properties, each proven by a named test through the real resolver with independent hand-derived oracles for both criteria. They are properties of the resolver, not conditions on a taxpayer's facts, because the capability grade rejects grades that hold only under a profile condition (option E there). A taxpayer whose fact is absent, ineligible or in conflict is already caught at run time, as an unresolved value or a blocking finding.
   - It dates every contributing income, expense and withholding row by the declared criterion (items 5 and 7).
   - It credits only `DECLARED_ON_LINKED_INVOICE` withholding with payment evidence, and leaves inferred and unknown rows out (the withholding-sources record).
   - Under an absent fact, it resolves rows that are the same under both criteria and leaves every straddling row unresolved.
   - It excludes accrued-but-unpaid withholding, and raises the rectification finding for a payment after the accrual year was filed, with a December invoice paid in January both before and after filing.
   - It excludes activity-rental rows from 0599 as `2026-11-01-export-parity-suffered-withholding-schemas-adr` section 7 sets out.
   - For casilla 06 also: it counts only withholding paid on or before the window end, under whatever the operator rules on the casilla 06 legal reading and endpoint.
   - The P04 reconciliation and the P05.S30 cross-check run over its output.

   Promotion itself remains the operator's ruling. Whether casilla 06 is promoted at all, or stays capped while 0599 is promoted, is the casilla 06 endpoint question, open below.

## Rationale

Primary text makes accrual the default. But the product cannot know that a given taxpayer is on the default: the election from an earlier return is invisible to a fresh profile, and the three-year minimum binds the taxpayer to it. Treating absence as undeclared is the only reading that cannot silently apply the wrong criterion. It also fits the schema convention and the payer-fact ruling. Preselecting `devengo` meets the operator's preference at the cost of one confirmation per profile. Holding back only straddling rows keeps most calculations usable while the fact is missing.

The TEAC unification criterion is the knockout on withholding timing. It binds AEAT's gestión and rules out both crediting before payment and crediting in the payment year (research, "TEAC unification doctrine"). The conservative Modelo 130 rule never over-credits a pago a cuenta. Its only cost is deferring a credit to the return where the law clearly allows it. The accrual-date fallback to `issued_at` comes from the invoicing regulation itself, not an assumption.

## Consequences

- **Gains:**
  - Accrual taxpayers credit invoice withholding in the right year.
  - 0169 becomes a declared, bound fact instead of an unbound box.
  - Late payments surface as explicit rectifications instead of a silent shift between years.
  - 0599 and casilla 06 each gain a promotion path whose bar is a set of tested resolver properties.
- **Costs:**
  - Every activity taxpayer answers one question per ejercicio.
  - Unlinked receipts become advisory under accrual, so invoice linking now matters for filing.
  - The devengo population moves from receipts and payments to issued and received invoices, which changes Modelo 130 casillas 01 and 02 and the Modelo 100 activity blocks for accrual taxpayers relative to today.
  - Expense rows with no linked document and no typed accrual rule become unresolved when they straddle a window under accrual.
- **Proposed amendment** to `2026-09-27-export-parity-renta-withholding-sources-adr`, Implementation Step 4, presented for approval and not applied. Current text: "and for 0599 the filed fourth-quarter Modelo 130 casilla 06". Proposed replacement: "and for 0599 the filed fourth-quarter Modelo 130 casilla 06 plus the itemised withholding imputed to the year but paid after the fourth-quarter window end, under `2026-11-01-export-parity-income-imputation-criterion-adr`".
- **Reconsider if:**
  - DGT or TEAC doctrine settles the Modelo 130 edge.
  - A later TEAC or Supreme Court ruling revises the 2012 criterion.
  - RIRPF art. 7 changes.
  - AEAT moves the election to a single taxpayer-level casilla.
- **Prior-record finding:** the suspected mis-citation of RIRPF arts. 94.1 and 108.1 in `2026-09-24-retenciones-workflow-modelo-123-count-authority-research` does not hold for its capital mobiliario scope, and needs no edit (research, "Prior-record check").

## Open questions for the operator

- Absent imputation fact. Does an absent criterion fact mean undeclared (the recommendation above, holding back only straddling rows), or the legal default `devengo`?
- Casilla 06 endpoint, shared with `2026-11-01-export-parity-binding-capability-grade-adr`. Is casilla 06 promoted through P05.S31 once item 9 holds, or does it stay capped?
- Four legal readings this record leaves unresolved, each now carried by the most conservative behaviour:
  - Modelo 130 casilla 06: may withholding imputed to the quarter but paid after its end, or remitted on an unpaid invoice, be deducted in that quarter (item 7)?
  - Change of criterion: which year receives amounts that RIRPF art. 7.4 would otherwise leave uncomputed (item 8)?
  - Partial payment: how is a partially paid invoice's withholding split between paid and unpaid (item 6)?
  - Three-year minimum: how are the three years counted, and is the election year the first (item 3)?
- A fifth reading, whether a repercutido ingreso a cuenta is credited in full under LIRPF art. 99.6, belongs to `2026-11-01-export-parity-suffered-withholding-schemas-adr` and is listed there.
