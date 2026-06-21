---
tags:
  - '#adr'
  - '#m390-iva-carry-boxes'
date: '2026-06-21'
modified: '2026-06-21'
related:
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
  - "[[2026-06-21-redeme-company-refund-research]]"
---

# `m390-iva-carry-boxes` adr: `Modelo 390 boxes 97 and 662 are one FIFO carry partition, not two independent period sums` | (**status:** `proposed`)

## Problem Statement

Modelo 390's two year-end IVA carry-forward boxes are modelled as two independent
registry relations that each sum a per-period Modelo 303 casilla, and both are
wrong:

- Box 97 ("Resultado de la última autoliquidación. A compensar") copies the 4T
  303 `iva.compensacion-generada-periodo` (= max(0, −resultado), the credit
  generated in 4T only), dropping the unapplied prior pending the 4T carries.
- Box 662 ("Cuotas a compensar generadas en el ejercicio, distintas a las
  incluidas en la casilla 97") sums the 1T–3T `iva.compensacion-generada-periodo`,
  counting every generated credit regardless of whether it was later applied or
  carried — including credits that ended up in box 97.

A campaign attempt to fix box 97 alone (point it at the 4T
`iva.compensacion-disponible-fin-periodo` = casilla 87 + generada) was reverted
because it introduced a DOUBLE-COUNT: the 1T–3T pending carried into 4T appears in
box 97 (via casilla 87) AND in box 662 (the 1T–3T generada sum). The two boxes are
not independent — they partition the year's pending credit, and the AEAT rule is
explicit that box 662 holds only credits "cuando NO estén incluidas en la casilla
97."

## Considerations

- The AEAT annual identity `[86] = [84] − [85] = [95] − [97] − [98] − [662]` binds
  the boxes: box 97 + box 662 must equal the year's total pending (no double count,
  no drop). Box 85 carries the prior-YEAR opening credit; box 662 is explicitly
  "generadas EN EL EJERCICIO".
- Whether a 1T–3T generated credit lands in box 97 (carried into the last period's
  autoliquidación), box 662 (generated-but-not-carried), or neither (applied during
  the year) depends on FIFO application netting across the whole year — it cannot
  be read from any single per-period 303 casilla.
- A FIFO carry projection ALREADY exists:
  `build_iva_compensation_carry_forward_report` produces lots with
  `generated_amount`, `applied_amount`, and `remaining_amount`. The (currently
  test-only) `cross_check_iva_compensation_annual_summary` already projects the
  boxes from these lots (`generated_amount` for the last period, `remaining_amount`
  for the others) — a third surface that must agree.
- This is the IVA-domain sibling of the M303 carry-reconciliation ADR: both are
  rooted in the disposition/application of credit being a whole-period fact, not a
  per-casilla value.

## Constraints

- **One mechanism (`one-aggregation-path-pull-equals-calculate`).** Box 97, box
  662, and the cross-check MUST derive from ONE FIFO partition; three independent
  computations re-open the drift this ADR closes.
- **No double-count, no drop.** The fix MUST satisfy the AEAT identity for the
  carried-pending case (the case both current relations get wrong), proven by a
  regression that asserts box 97 + box 662 against an external oracle, with a
  non-zero carried-pending scenario.
- **Behaviour-preserving for the zero-carry case.** Every existing M390 continuity
  test seeds zero prior pending; the new model MUST leave those green (box 97 =
  generada, box 662 = 1T–3T remaining collapse to the current values when nothing
  is carried).
- **Cross-year compounding.** A wrong year-end carry injects into next year's
  opening (`carried-observations-stamp-their-revision`), so the regression must be
  multi-period.

## Implementation

- **Replace the two per-period relations with a FIFO-projected pair.** Drive box 97
  and box 662 from `build_iva_compensation_carry_forward_report` over the year's
  303 period states: box 97 = the saldo the LAST period carries forward (the
  remaining of all lots still pending at the last period, i.e. the last period's
  disponible), box 662 = the remaining of credits generated in non-last periods
  that are NOT carried into box 97 (generated-not-applied-not-in-97). Applied
  credits appear in neither.
- **Reconcile the cross-check to the same partition.** Update
  `cross_check_iva_compensation_annual_summary` so its `last_period` and
  `generated_not_in_last` use the same lot quantities as the box projection,
  removing the relation-vs-cross-check divergence.
- **Retire the two registry relations** (`modelo-390-rel-303-compensacion-ultimo-
  periodo`, `…-generada-ejercicio-no-97`) and their dependency-classification /
  construct entries once the FIFO projection owns the boxes — or keep the relations
  as the transport but feed them the FIFO-derived values rather than raw per-period
  casillas. The transport choice is a plan-level decision; the invariant is one
  FIFO partition.

## Rationale

The boxes are a partition of one quantity (the year's pending credit) governed by
FIFO application, so they must be computed together from the FIFO projection that
already exists, not as two independent per-period sums. Fixing either box alone
double-counts or drops the carried pending (demonstrated and reverted). Grounding
both in the lot model satisfies the AEAT identity and the pull-equals-calculate
discipline, and reuses verified infrastructure.

## Consequences

- **Gain:** box 97 + box 662 correctly sum the year's pending with no double-count
  or drop; the operator-facing annual summary reconciles with the 303 carry chain
  and the cross-check.
- **Difficulty:** moves two boxes from declarative registry relations to an
  application-layer FIFO projection — a calc-path change touching three surfaces.
- **Pitfall:** fixing one box in isolation (the reverted attempt) — the regression
  asserting box 97 + box 662 on a carried-pending scenario guards against it.
- **Pitfall:** the FIFO "not carried into box 97" partition is subtle for a
  taxpayer who does not carry everything forward; the plan must enumerate the
  carry / don't-carry / applied cases with grounded expectations.

## Codification candidates

- **Rule slug:** `m390-carry-boxes-are-one-fifo-partition`.
  **Rule:** Modelo 390 box 97 and box 662 (and the annual cross-check) MUST be
  derived together from the single IVA-compensation FIFO carry projection so they
  partition the year's pending credit with no double-count or drop, never as two
  independent per-period 303-casilla sums; the AEAT identity
  `[86]=[84]−[85]=[95]−[97]−[98]−[662]` is the regression oracle.
