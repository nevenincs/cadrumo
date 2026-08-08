---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c1a4ffa76009245c797b0cd488399aeb35424e86400e27dd290c7f6c9a9987b5'
step_id: 'S07'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add the re-capture divergence diff comparing a fresh FiledDeclaracionObservation against the prior stamped observation for the same modelo, ejercicio and period key, verified by a test that re-captures a fixture with one changed casilla value and asserts exactly one WARNING Notice naming that casilla

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add `casillas_a_recapture_would_change`, deriving the changed set from the captured casillas.
- Add `recapture_divergence_notices` emitting one WARNING per re-captured filing whose values changed.

## Outcome

Derived from the observed casilla set rather than a hand-listed field list, for
the same reason the shipped invoice reconfirm diff is: the failure this exists to
catch is a comparison that OMITS a casilla, and a hand-listed set is precisely how
that omission arrives.

Only casillas present on BOTH sides are compared. A casilla the fresh capture read
and the stored revision never held is not a changed value — it is a wider
extraction — and firing on every extraction improvement would train the operator
to ignore the alert.

An unreadable fresh token is skipped rather than reported as changed, because a
parse failure is not evidence of an amendment and claiming one would put a false
correction in front of the operator. The kind check ahead of the conversion is
what makes that the only reachable failure.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_history_discovery.py -q -n0
    38 passed in 16.82s

One test reads the function's own source and asserts no literal casilla id appears
in it, so the derivation cannot quietly become a fixed list.

## Notes

Mirrors the shipped censo-divergence shape found by semantic search rather than
by name: a standing advisory, never a silent auto-resolve, because AEAT
legitimately permits a complementaria and refusing the write outright would be
wrong.
