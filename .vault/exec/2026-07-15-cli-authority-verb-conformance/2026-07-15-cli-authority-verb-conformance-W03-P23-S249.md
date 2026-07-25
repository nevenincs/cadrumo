---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S249'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove identical latest selection and history ordering across all capture routes, their distinct failure policies, and preservation of the separate strict IVA compensation persistence path

## Scope

- `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`
- `src/cadrumo/application/live/tests/test_filed_bulk_capture.py`
- `src/cadrumo/application/live/tests/test_iva_remote_state_acquisition.py`

## Description

- Confirm all three cited probe modules exist and carry real cases rather than placeholders.
- Locate a named probe for each of the step's three distinct claims.
- Run the three modules with explicit marker selection and confirm a non-zero collected count.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

All three cited modules exist and are substantial, carrying thirty, six and twenty-one cases respectively. Each of the step's three claims has a probe named for it, so the closure rests on identified cases rather than on an aggregate pass.

Identical selection and ordering across routes is proven by a probe asserting that all capture routes share one selection and ordering authority, and reinforced by a second that asserts the finalizer's emitted keys and the persistence module's batch keys are equal for the same input. Ordering is covered on its own axis too, with probes pinning latest-active selection per period, the annual declaration ordering after the periodic ones for the IVA modelo, and the preservation of numeric period order for non-IVA rows alongside IVA rows in the same history. That last one matters because it is where a single global sort would break one modelo family to satisfy the other.

The distinct failure policies are proven by a matched pair rather than one case: one probe asserts the best-effort finalizer reports an incomplete observation into its failure rows and continues, and its counterpart asserts the fail-fast finalizer raises on the same input. A pair is the right shape here, since either case alone would pass against a finalizer that ignored the policy argument.

Preservation of the strict IVA compensation path has its own named probe asserting the finalizer does not disturb it, backed by further cases covering strict persistence storing and reloading the latest record, promotion of an active declaration over a later non-active one, and the refusal to persist a period that carries only non-active declarations. The strict path is therefore held separately rather than folded into the shared finalizer, which is what the step requires.

Run at the current commit with explicit marker selection: fifty-seven collected and fifty-seven passed. The count is recorded because the default marker selection would have selected nothing for these modules and exited green, so a bare path invocation here is not a verification. No change was needed or made.

## Notes

Semantic code search was degraded and reported itself healthy, with an empty degraded-reasons list, so the probes backing each claim were located by grepping case names in the three cited modules rather than by searching for the behaviours.

Unlike the four other steps in this handover, this step's file citations are accurate: all three named modules exist and hold the proofs the step describes. That is worth recording precisely because the campaign's other citations drifted; the drift is not uniform, so citations have to be checked individually rather than assumed bad.

The parity probe between the finalizer and the batch persistence function is load-bearing for the neighbouring step's conclusion as well as this one. It is the reason the batch function is a parity anchor rather than a duplicate to delete, so removing that function later would silently remove this step's strongest cross-route equality proof.
