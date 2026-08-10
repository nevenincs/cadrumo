---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ade7430cd984d817124f4f58c8f97fce77e334a2cd7d337d4193b07817734fa0'
step_id: 'S20'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-adr]]"
---

# Establish the populated-enough scoping condition

## Scope

- `src/cadrumo/application/modelo`
- `src/cadrumo/application/calculations`

## Description

- Enumerate what the persisted calculation revision actually records, from the
  strict model rather than from an assumption about what a bucket holds.
- Establish that the condition is derivable, and at what granularity.
- Resolve the condition per casilla over the revision's own formula graph,
  reusing the registry's exported expression-reference helpers.
- Return it as a scope the existing comparison primitive already accepts, so no
  second differ is introduced.
- Assert both directions: an empty bucket surfaces nothing, a populated one
  still surfaces its disagreement.
- Assert the anti-circularity axis separately, because it is the one an
  implementer would most plausibly get wrong.

## Outcome

The row's two permitted outcomes were "a stated condition evaluable from
persisted state" or "a recorded finding that no such condition is derivable".
The answer is the first. The condition is derivable, and the row's pessimism
about it rested on asking the question at the wrong granularity.

WHAT THE ROW ASSUMED. That population is a property of a bucket — that a profile
is either populated or empty, and that the persisted state might not carry
enough to tell which. Asked that way the row is nearly unanswerable, because a
bucket holding one figure out of forty is neither.

WHAT IS ACTUALLY DERIVABLE. Population is a property of a CASILLA, and at that
granularity the persisted state is sufficient. `CalculationRevision` records
`input_values_by_casilla_id`, `binding_overrides`, `row_binding_values`,
`relation_overrides` and `source_transaction_ids`. The registry revision supplies
the formula graph, and the expression-reference helpers the registry already
exports walk a formula to its casilla and binding references without any new
traversal machinery being written. So for each casilla the input closure is
computable, and the question "did this revision supply anything that reaches
this casilla" is answerable from persisted state alone.

A revision that supplied nothing anywhere is therefore comparable at no casilla,
which is exactly the freshly-onboarded case the row was opened for: the empty
bucket produces no divergence rather than a divergence on essentially every
reconciled casilla. A revision that supplied one figure is comparable at the
casillas that figure reaches and at no others, which a whole-revision gate could
not express — it would either silence the one thing the operator has to say or
surface the thirty-nine they do not.

WHAT DOES NOT COUNT AS POPULATION, AND WHY THIS IS THE LOAD-BEARING PART. Carry
bindings — `previous_filing` and `relation_prefill` — and relation references are
excluded. Their values are read back from the same filed-observation store the
comparison's filed side is read from, so counting them would let the scope be
satisfied by the very figures under comparison, and the detector would then
report agreement between AEAT and AEAT as though it were a local calculation
agreeing with a filing. That is a circularity, not a conservatism, and it is
asserted directly rather than left to review.

WHAT THIS DELIBERATELY DOES NOT CATCH, and this sentence is the record's, not
the ledger's. A taxpayer whose true figure is non-zero and who supplied nothing
leaves the casilla unpopulated, so no divergence is raised and a real
under-declaration goes unreported on this channel. That is a false-negative bias
and it was chosen, not overlooked: the alternative fires on every casilla of
every empty bucket, which is the alert fatigue the unconsumed-declarable-IVA
rule exists to prevent and which trains an operator to ignore the channel. It
must not be read as coverage of the absent-input case. That case needs a
different signal, and nothing here supplies one.

A SECOND, SMALLER FALSE NEGATIVE. The clause that admits bucket-local evidence
approximates "the bucket holds evidence" with "this revision consumed ledger
transactions", so a bucket populated only with invoices and no ledger
transactions scores as empty. Also the safe direction, also stated rather than
smoothed over.

THE DETECTOR IS NOT WIRED. The row forbids it and nothing here wires it. What
landed is the scope and its justification.

## Notes

THE ROW'S PREMISE FOR ITS SUCCESSOR IS FALSIFIED, and the successor must be
re-read against this rather than executed as written. The row states that both
sides of the comparison persist in the same bucket and nothing joins them. A
join exists: `verify_filed_state` in `src/cadrumo/application/registry` loads a
captured filed observation, runs a live registry calculation and compares them
per casilla, and it is reachable from the shipped CLI. It avoids the emptiness
problem by a different design — it takes the filed observation's own input
casillas as the calculation inputs, so no local emptiness enters the comparison
at all — which means it measures whether the engine reproduces AEAT's arithmetic
from AEAT's inputs, not whether the taxpayer's own calculation disagrees with
what they filed. Those are different questions, and the second is still
unanswered. But "nothing joins them" is not true of the tree and must not be
repeated.

A DUPLICATE COMPARISON AUTHORITY IS OPEN AND IS NOT CLOSED BY THIS ROW.
`detect_casilla_divergences` and `compare_calculation_to_filed_observation` both
classify per-casilla disagreement between a local calculation and filed AEAT
values. They differ on at least three axes — tolerance handling, whether
regulatory provenance rides each row, and how the three disagreement categories
are shaped — so which subsumes which is a real judgement and not a mechanical
merge. Naming it here rather than acting on it, because closing it is a change
to a surface this row does not own.

VERIFICATION WAS NOT RUN BY THE AUTHOR. The suite authority ran it. The first
submission was refused before execution: the new test module carried no
top-level marker, so no lane selected it and a targeted run would have reported
no tests ran and exited 5 — a status that reads as success. Both anti-vacuity
guards in the module would have been unreachable from any lane, and the module
would have red the marker-integrity ratchet on the next run by anyone. Corrected
in its own commit rather than folded into the feature commit, so the gap is
legible in history.
