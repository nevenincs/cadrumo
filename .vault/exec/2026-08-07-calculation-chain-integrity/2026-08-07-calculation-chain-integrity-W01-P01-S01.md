---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:33a501f0cd60a87ee09002227901ca66fa196548609a6fa7f2d8d2c5d813b568'
step_id: 'S01'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W01.P01.S01

## Outcome

Read the T-05 prior art before designing. It did already prescribe the fix, which is the answer this Step exists to get, and it is why the rest of the Phase now reads differently than when it was written.

## What T-05 prescribes

`.vault/reference/2026-05-15-linkage-design-audit-reference.md` section T-05, "Hard-coded constants outside the registry", describes exactly this shape: a mapping from a domain concept to a casilla id declared as a module-level Python constant rather than a registry field, where "the registry TOML and the Python constant can diverge silently; no load-time cross-check enforces agreement."

Its 2026-06-29 current-state correction is the load-bearing part. The Renta first-slice portion is recorded CLOSED, and closed **without** moving the map into the registry: the live code keeps `FIRST_SLICE_EXPENSE_CASILLAS` as a Renta-domain mapping and registers a `CrossDomainSnapshotCheck` that validates every routed casilla against the Modelo 100 snapshot before calculation.

So T-05's established remedy is not "declare it in the registry". It is "keep the constant in its owning domain, and cross-check it against the real snapshot at build time". The summary table confirms the scope: R025 and R026 closed, the residue being "other unvalidated module-level casilla maps".

## Consequence for this Phase

`W01.P01.S02` and `W01.P01.S03` are written the other way round: give the binding family a registry-declared output casilla, then retire the hardcoded override. That is the design T-05 considered and did not adopt for the sibling case.

This is not hypothetical. The registry-field approach was implemented and then reverted in commit `fc0d0353b2` on precisely this ground. Reading the prior art first is what this Step asked for, and doing so would have prevented the round trip.
