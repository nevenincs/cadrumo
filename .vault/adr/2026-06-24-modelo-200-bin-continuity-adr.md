---
tags:
  - '#adr'
  - '#modelo-200-bin-continuity'
date: '2026-06-24'
modified: '2026-06-24'
related:
  - '[[2026-06-21-eoy-final-calculation-audit]]'
---

# `modelo-200-bin-continuity` adr: `M200 BIN closing balance must be reconciled to the roll-forward by a no-silent continuity predicate` | (**status:** `proposed`)

## Problem Statement

Modelo 200 casilla `00671` (`is_bin_total_pendiente`, "Detalle compensación bases imponibles
negativas — TOTAL — Pendiente de aplicación en períodos futuros") is a bare `input_kind = "manual"`
input with **no continuity enforcement**. It is the closing stock of negative tax bases (BIN)
carried to future years. Its value is bound by an arithmetic roll-forward from the opening stock,
this period's compensation, and any BIN generated this period — but nothing in the registry checks
that the operator-entered `00671` actually reconciles to that roll-forward. An operator can enter any
closing balance; a silently-wrong `00671` propagates an incorrect BIN stock into every future year's
compensation (the defect compounds across years, like the cross-period carry class).

The BIN area already carries guards for the *applied* amount — `compensacion ≤ art-26 límite`
(`cap_le_when_positive(["DP200014:00547", "DP200014:bin-aplicada-maxima"])`) and
`compensacion ≤ opening stock` (`cap_le_when_positive(["DP200014:00547", "00670"])`). What is missing
is the *closing-balance continuity*: that `00671` equals opening minus applied plus generated.

## Considerations

- The roll-forward inputs all exist as casillas: `00670` (opening total pending, `input_kind = "bound"`),
  `DP200014:00547` (compensación BIN aplicada this period), `DP200014:00552` (base imponible, computed —
  negative when a new BIN is generated), and `00671` (closing total pending).
- The AEAT Modelo 200 manual describes the per-year "Pendiente de aplicación en períodos futuros"
  columns (split by the art. 16.5/83 límite vs resto) — a per-year-bucket roll-forward. The TOTAL-level
  identity holds regardless of the per-year split: closing total = opening total − applied + generated.
- Total-level continuity invariant (grounded): `00671 = 00670 − DP200014:00547 + max(0, −DP200014:00552)`.
- The verification-predicate language currently exposes only `implies_nonzero(...)` and
  `cap_le_when_positive(...)`; it has no primitive for an arithmetic balance/continuity equality.

## Constraints

- **Regulated, compounding value.** A wrong `00671` mis-states future-year BIN stock; the guard must
  be grounded in the AEAT roll-forward rules, not invented.
- **Do not over-compute.** Unlike the cuota-líquida fix (where the manual casilla was safely made
  computed), `00671` is the total of operator-entered per-year detail rows (`00646`…`03404`) that carry
  per-year límite-column splits a single total formula does not capture. Converting `00671` to a bare
  computed value risks diverging from the operator's per-year detail. The closing balance stays a
  manual/detail-sourced figure; the registry *reconciles* it rather than *replacing* it.
- **Advisory, not blocking.** A legitimately-zero closing (all BIN applied, none generated) must remain
  permissible; the guard fires only on genuine discontinuity (`no-silent-under-declaration` at the
  notice level, mirroring the existing M200 advisories).
- **New predicate primitive** is a shared calc-engine surface; its evaluator must be added with real
  tests and must not weaken existing predicates.

## Implementation

- Add one balance-check predicate primitive to the verification-predicate evaluator — a continuity
  form asserting a target casilla equals an arithmetic expression over other casillas within a cent
  tolerance (e.g. `balances(target, [terms…])` or a continuity helper), returning an advisory finding
  on mismatch. Keep it general enough to serve other roll-forward continuities (it is the predicate
  analogue of the missing arithmetic primitive).
- Declare one M200 verification predicate grounding the BIN total continuity:
  `00671 = 00670 − DP200014:00547 + max(0, −DP200014:00552)`, ADVISORY severity, with `legal_refs`
  to LIS art. 26, and a `source_citation` to the AEAT manual's "Pendiente de aplicación en períodos
  futuros" roll-forward clause.
- Real tests (grounded, not tautological): a continuous filing (closing reconciles → no finding); a
  silently-dropped carryforward (operator zeroes `00671` while opening exceeds applied → advisory
  fires); a legitimately-zero closing (all applied, none generated → no false fire); a
  BIN-generated-this-period case (negative base adds to closing). Expected values derived from the
  AEAT roll-forward rule, not from the predicate under test.

## Rationale

The defect is the cross-period-carry class applied to BIN stock: a manual closing balance with no
reconciliation silently corrupts future-year compensation. The fix mirrors the established M200
verification-predicate pattern (the base-imponible and BIN-límite advisories) and the cross-period
discipline that a carried value must be re-confirmable, not trusted blind. Reconciling rather than
recomputing respects the per-year detail the operator owns while still making a gross discontinuity
loud. The single new balance primitive is the minimum engine addition; it generalises to other
roll-forward continuities the engine will need.

## Consequences

Gains: a silently-wrong BIN closing balance becomes a surfaced advisory instead of a compounding
future-year error; the new balance primitive unlocks continuity guards across the engine. Difficulties:
adding a predicate primitive touches the shared evaluator (needs careful tests); the total-level
invariant is a simplification of the per-year límite-split detail, so the predicate must be framed as a
TOTAL reconciliation, not a per-year assertion. Pitfalls: a blocking (rather than advisory) guard would
refuse legitimate edge cases (full application, generation timing); the invariant must include the
generated-this-period term or it would false-fire on a loss year.

## Codification candidates

- **Rule slug:** `cross-period-carry-balances-are-reconciled`.
  **Rule:** Every manually-entered cross-period carry/closing-balance casilla (BIN stock, pending
  credits, recargo carryforward) MUST be reconciled to its roll-forward (opening − applied + generated)
  by a grounded continuity predicate that surfaces at least an advisory on mismatch; never trust a bare
  manual closing balance that silently propagates to future periods. Promote after this guard lands and
  the lesson holds across one cycle.
