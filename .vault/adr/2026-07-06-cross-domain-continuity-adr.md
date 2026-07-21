---
tags:
  - '#adr'
  - '#cross-domain-continuity'
date: '2026-07-06'
modified: '2026-07-17'
related:
  - "[[2026-07-06-cross-domain-continuity-research]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-iva-classification-enrichment-adr]]"
---

# `cross-domain-continuity` adr: `iva cash accounting treatment for modelo 303` | (**status:** `accepted`)

## Problem Statement

W05.P24.S281 asks to add a criterio de caja ledger axis and wire Modelo 303
casilla 62. The open S287 planning blockage exists because the previous accepted
IVA classification ADR explicitly excluded casilla 62 from intracom/export scope
without deciding how cash accounting should be represented.

The risk is modelling cash accounting as another `IvaCategory`. That would
collapse two independent axes: the operation's VAT treatment and the timing regime
that decides when output VAT accrues, when input VAT becomes deductible, and what
additional informational totals Modelo 303 requires.

## Considerations

Ley 37/1992 art. 75 provides the general devengo rule. The cash-accounting
regime is governed by arts. 163 decies through 163 quinquiesdecies. Art. 163
terdecies changes devengo and deduction timing for taxpayers using the regime.
Art. 163 quinquiesdecies changes deduction timing for non-regime recipients of
operations affected by the regime. Art. 163 duodecies also excludes operations
such as art. 21 exports and art. 25 intra-community supplies from the regime.

AEAT's official cash-accounting obligations page states that Modelo 303 includes
both VAT accrued under cash accounting and informational totals for operations as
if the general devengo rule had applied. The official Modelo 303 form labels
boxes 62/63 as the supply base/cuota pair for affected operations that would have
accrued under art. 75, and boxes 74/75 as the acquisition base/cuota pair for
operations to which the regime applies or by which the recipient is affected.

The current registry declares boxes 62, 63, 74, and 75 in both M303 revisions as
optional manual rows. The legal refs on those rows are generic; the legal
catalogue does not yet define `ley-37-1992:art-75` or the cash-accounting
articles. S281 must repair legal grounding before changing any of those rows to
bound or computed.

## Considered options

1. Add `CRITERIO_CAJA` to `IvaCategory`.
   Rejected. A cash-accounting sale still needs its domestic, exempt, reverse-charge,
   or other IVA treatment. Replacing that category with a regime marker loses the
   real tax classification and conflicts with art. 163 duodecies exclusions.

2. Add an independent cash-accounting regime axis plus payment/collection evidence.
   Accepted. The ledger can preserve the operation's `IvaCategory`, record whether
   the taxpayer is applying the regime or receiving an affected invoice, and decide
   settlement timing from real cash-flow evidence.

3. Keep boxes 62/63/74/75 manual.
   Rejected for S281. Manual fallback is acceptable until implementation, but S281's
   purpose is to remove the known planning gap. Leaving the boxes manual keeps the
   silent-under-reporting risk for taxpayers who use or receive cash-accounting
   operations.

4. Bind only casilla 62.
   Rejected. Casilla 62 is not a standalone settlement result; it is one member of
   the official cash-accounting informational set. Binding it alone would make the
   registry structurally inconsistent and omit the paired cuota and acquisition-side
   data.

## Constraints

- Do not extend `BusinessClassification`; the accepted IVA classification ADR keeps
  it as a business/personal processing gate.
- Do not add a cash-accounting value to `IvaCategory`; the operation's tax category
  remains authoritative for rate, exemption, intracom, export, and not-subject
  routing.
- S281 must add legal catalogue entries for LIVA art. 75 and the cash-accounting
  art. 163 decies-undecies-duodecies-terdecies-quaterdecies-quinquiesdecies family,
  grounded in the bundled BOE corpus and cross-checked against live BOE/AEAT
  sources.
- S281 must treat the M303 cash-accounting boxes as a set: 62/63 for supplies and
  74/75 for acquisitions. It may stage implementation, but verification must make
  any intentionally deferred member explicit.
- The implementation needs real payment or collection evidence. Invoice date alone
  is only the art. 75 informational projection, not the cash-accounting settlement
  date.

## Implementation

S281 should introduce an independent cash-accounting axis on the ledger transaction
or IVA ledger observation surface, with at least these semantics:

- no cash-accounting effect;
- taxpayer applies the special regime to an issued operation;
- taxpayer receives an operation affected by the supplier's special regime.

The model must carry enough cash-flow evidence to determine total or partial
collection/payment dates and amounts, plus the statutory fallback date when the
operation remains unpaid at 31 December of the following year. The original IVA
category remains present and continues to drive ordinary tax-category routing.

Aggregation then projects two surfaces from the same evidence:

- Settlement routing: output VAT and input deduction enter the normal M303
  settlement totals only when art. 163 terdecies or art. 163 quinquiesdecies says
  devengo or deduction has arisen.
- Informational routing: boxes 62/63 and 74/75 report the affected operations under
  the general art. 75 projection required by the form and AEAT obligations guidance.

Before any casilla row is changed from manual, the registry legal refs for those
boxes and any new bindings must cite the specific cash-accounting provisions, not
only generic art. 88/art. 92/form-order refs.

## Rationale

The research shows cash accounting is a timing and reporting regime, not a taxable
operation category. Modelling it as `IvaCategory.CRITERIO_CAJA` would make the
ledger unable to distinguish a domestic 21 percent sale under cash accounting from
the same sale outside the regime, and would also blur operations that the law
explicitly excludes from the regime, including art. 21 exports and art. 25
intra-community supplies.

The accepted `2026-05-27-iva-classification-enrichment-adr` remains binding for
intracom/export classification and already closes the original D1-D4 decision set
for S91-S95. This ADR adds the missing S281 decision: cash accounting is its own
axis with payment evidence and a full 62/63/74/75 projection, not a new
classification enum member and not a casilla-62-only binding.

## Consequences

- S281's plan text should be interpreted as "add a cash-accounting ledger axis",
  not literally as "add a criterio_caja `IvaCategory` variant".
- The implementation scope is larger than a single binding: it needs legal
  catalogue additions, ledger evidence fields, settlement timing rules, and the
  four informational M303 boxes.
- The current manual boxes remain acceptable only until S281 lands. Once S281
  starts, partial wiring must fail loudly rather than leaving 63/74/75 manual and
  silently inconsistent with 62.
- Future tests need real-behavior scenarios with collection/payment dates and an
  anti-tautology mutation that changes the cash-flow date or amount and proves both
  settlement timing and informational totals react differently.
