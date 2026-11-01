---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-11-01'
modified: '2026-11-01'
body_schema: 'body-v2'
body_hash: 'sha256:024c9e714a9313c7340b725444b73b1c531a6930b4ff9aa020136acbb6580032'
related:
  - "[[2026-11-01-export-parity-income-imputation-criterion-research]]"
  - "[[2026-09-27-export-parity-renta-withholding-sources-adr]]"
  - "[[2026-09-23-calendar-obligations-payer-fact-declaration-state-adr]]"
---
# `export-parity` adr: `income imputation criterion` | (**status:** `proposed`)

## Problem Statement

The ledger dates every activity income row and its withholding by bank date (`src/cadrumo/application/aggregation/renta_income_ledger.py:926-940`). Bank dating is the cash-basis (cobros y pagos) criterion. In law, the default is accrual (devengo), and cash basis is an election the taxpayer declares in Modelo 100 casilla 0169. That casilla is currently unbound. As a result, for an accrual taxpayer, a December invoice paid in January credits the wrong year in both Modelo 100 casilla 0599 and Modelo 130 casilla 06.

The accepted withholding-sources ADR keeps 0599 advisory until this temporal rule is grounded. `2026-11-01-export-parity-income-imputation-criterion-research` now grounds it. This record decides how Cadrumo represents the taxpayer's criterion, and how income and withholding are keyed under each criterion. It also defines the evidence bar for presenting 0599 for promotion. The operator ruled on 2026-11-01 that the criterion is a typed profile fact.

## Considerations

- Accrual is the legal default, and cash basis is an election available only outside Código de Comercio accounting. The election covers all activities, must be declared in every return, and lasts at least three years (research, "Accrual is the default" and "Cash-basis election").
- Withholding is imputed to the same year as its income. The right to deduct it arises only on payment. When the accrual year was filed before the payment, that year is rectified through an autoliquidación rectificativa for IRPF 2024 and later. The withholding is never credited in the payment year (research, "TEAC unification doctrine"; TEAC 00/03187/2011, DGT V1429-19, V0486-14 and V1177-25).
- Modelo 130 follows the same imputation (DGT V3298-15). Whether withholding paid after the quarter, or remitted on an unpaid invoice, may be deducted in that quarter is not settled in primary text (research, "Modelo 130").
- An invoice with no operation date documents an operation on its issue date (RD 1619/2012 art. 6.1.i). An advance-payment date is not an accrual date (research, "Accrual date").
- The profile schema already treats operator facts as "absent means undeclared" (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:937`). `2026-09-23-calendar-obligations-payer-fact-declaration-state-adr` rejects defaulted answers as silent under-declaration.
- The operator prefers accrual as the default answer.
- `no-silent-under-declaration`, and the rule that absent, unknown, advisory and proven-zero stay distinct (the project's aggregation and completeness invariants).

## Considered options

- **Absent means devengo.** This matches the legal default and costs no question. Rejected: a fresh or imported profile cannot see a cash-basis election made in an earlier return, so the product would silently apply the wrong criterion for up to three years. It also contradicts the schema convention and the payer-fact ruling.
- **Absent means undeclared, with devengo as the proposed answer.** The wizard preselects devengo and the operator confirms it in one step. Until then, only the outputs the criterion can change are held back. Chosen.
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

We will add a typed, effective-dated imputation-criterion profile fact. Ledger income and withholding are keyed by the fact's criterion. Withholding is credited only on payment, and payment after filing becomes a rectification finding. Casillas 0169, 1443 and 1487 are bound from the fact. Work is bounded to plan Steps P05.S21, P05.S22 and P05.S08.

1. **Profile fact (P05.S21).**
   - Key: `activity_income_imputation_criterion` in the `irpf` section.
   - Values: `enum_values = ["devengo", "cobros_y_pagos"]`, `effective_dated = true`, one value per ejercicio, sensitivity `financial`.
   - Model selector: `irpf.activity_income_imputation_criterion`.
   - `legal_refs`: `rd-439-2007:art-7`, `ley-35-2006:art-14` and `ley-27-2014:art-11`.
   - Absent means undeclared, never `devengo`. The wizard question preselects `devengo` as the proposed answer and explains when cash basis is open. A non-interactive setup leaves the fact absent; only an interactive answer or an explicit CLI flag writes it.
2. **Eligibility companion fact (P05.S21).**
   - Key: `codigo_comercio_accounting`, an optional, effective-dated boolean meaning "obliged to keep, or keeps voluntarily, accounting under the Código de Comercio" (RIRPF arts. 7.2.3.º and 68.2).
   - It is asked only when `cobros_y_pagos` is chosen.
   - `cobros_y_pagos` is admissible for an ejercicio only when `estimation_regime` is declared and `codigo_comercio_accounting` is `false`.
   - Ineligible means `true`, or an undeclared regime or companion. In that case, verify raises a blocking finding that names the provision. Calculation does not fall back to devengo silently.
3. **Three-year minimum (P05.S21).**
   - Enforced as a finding, not a refusal. Verify blocks an ejercicio declared `devengo` when the fact history, or a captured filed Modelo 100 carrying 0169, 1443 or 1487, shows a `cobros_y_pagos` election within the two preceding ejercicios.
   - Exception: the election lost effect under art. 7.2.2.º, shown by `codigo_comercio_accounting = true` in the changed year.
   - A conflict between the profile history and a filed observation also blocks.
   - Hypothesis: counting the election year as the first of the three years.
4. **Casilla binding (P05.S21; the Step's paths widen to the Modelo 100 registry as a routine plan correction, serialized with the other Modelo 100 edits).**
   - Bind 0169 in each estimación directa activity block, and 1443 and 1487 in the objetiva blocks, at the 2020 baseline, inherited forward.
   - Each casilla is marked iff the fact is `cobros_y_pagos` and blank iff it is `devengo`.
   - Absent leaves the casilla unresolved, which blocks export rather than writing blank.
   - Add `rd-439-2007:art-7` to the three casillas' `legal_refs`.
5. **Ledger keying (P05.S22).**
   - Under `cobros_y_pagos`: income and withholding are dated by receipt, meaning bank `value_date`, else `booked_date`, as today.
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
   - Hypothesis: partially paid invoices stay advisory until an apportionment rule is grounded.
7. **Modelo 130 (P05.S22).**
   - Casillas 01 and 02 follow the criterion within the cumulative window.
   - Casilla 06 counts withholding imputed to the window and paid on or before the window end.
   - Withholding imputed to the window but paid later, and withholding remitted on an unpaid invoice, are excluded and surfaced as advisory. Whether either may be deducted in that quarter is an operator question. Exclusion only defers the credit to the annual return.
   - The Step 4 fourth-quarter cross-check therefore compares 0599 against casilla 06 plus the itemised withholding paid after the window end, so a legitimate timing difference does not block.
8. **Change of criterion (P05.S22).**
   - Under RIRPF art. 7.4, rows already imputed in the prior year under devengo are excluded from a first cash-basis year, with a finding.
   - Rows that both criteria would leave uncomputed, on a change from cash to accrual, stay unresolved and block. The year that receives them is an operator question.
9. **0599 promotion (P05.S08).** S08 presents promotion for operator ruling only when all of these hold:
   - This record is accepted.
   - The fact and its eligibility are declared for the ejercicio with no open finding.
   - Every contributing row has a criterion-consistent date and `DECLARED_ON_LINKED_INVOICE` withholding with payment evidence.
   - Independent hand-derived oracles pass through the real path for both criteria, with a December invoice paid in January before and after filing.
   - The P04 reconciliation runs with the criterion-aware fourth-quarter cross-check.

   Promotion itself remains the operator's ruling.

## Rationale

Primary text makes accrual the default. But the product cannot know that a given taxpayer is on the default: the election from an earlier return is invisible to a fresh profile, and the three-year minimum binds the taxpayer to it. Treating absence as undeclared is the only reading that cannot silently apply the wrong criterion. It also fits the schema convention and the payer-fact ruling. Preselecting `devengo` meets the operator's preference at the cost of one confirmation per profile. Holding back only straddling rows keeps most calculations usable while the fact is missing.

The TEAC unification criterion is the knockout on withholding timing. It binds AEAT's gestión and rules out both crediting before payment and crediting in the payment year (research, "TEAC unification doctrine"). The conservative Modelo 130 rule never over-credits a pago a cuenta. Its only cost is deferring a credit to the return where the law clearly allows it. The accrual-date fallback to `issued_at` comes from the invoicing regulation itself, not an assumption.

## Consequences

- **Gains:**
  - Accrual taxpayers credit invoice withholding in the right year.
  - 0169 becomes a declared, bound fact instead of an unbound box.
  - Late payments surface as explicit rectifications instead of a silent shift between years.
  - 0599 gains a concrete promotion bar.
- **Costs:**
  - Every activity taxpayer answers one question per ejercicio.
  - Unlinked receipts become advisory under accrual, so invoice linking now matters for filing.
  - The devengo population moves from receipts to issued invoices, which changes Modelo 130 casilla 01 for accrual taxpayers relative to today.
- **Proposed amendment** to `2026-09-27-export-parity-renta-withholding-sources-adr`, Implementation Step 4, presented for approval and not applied. Current text: "and for 0599 the filed fourth-quarter Modelo 130 casilla 06". Proposed replacement: "and for 0599 the filed fourth-quarter Modelo 130 casilla 06 plus the itemised withholding imputed to the year but paid after the fourth-quarter window end, under `2026-11-01-export-parity-income-imputation-criterion-adr`".
- **Reconsider if:**
  - DGT or TEAC doctrine settles the Modelo 130 edge.
  - A later TEAC or Supreme Court ruling revises the 2012 criterion.
  - RIRPF art. 7 changes.
  - AEAT moves the election to a single taxpayer-level casilla.
- **Prior-record finding:** the suspected mis-citation of RIRPF arts. 94.1 and 108.1 in `2026-09-24-retenciones-workflow-modelo-123-count-authority-research` does not hold for its capital mobiliario scope, and needs no edit (research, "Prior-record check").
