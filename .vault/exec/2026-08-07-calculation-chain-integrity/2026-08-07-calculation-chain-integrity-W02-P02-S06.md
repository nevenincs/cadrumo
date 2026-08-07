---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:fcda7b7cd180c63351e4d6507529a8f529c56342441ec9d5ed3d2a325bb3caea'
step_id: 'S06'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---

# Author the decision record selecting registry-build reachability as primary with the implies-nonzero coverage floor layered, rejecting prior-period comparison on its false-fire profile

## Scope

- `.vault/adr/`

## Description

- Authored the decision body of `2026-08-07-calculation-chain-integrity-adr` (Problem Statement through Consequences), grounded in `2026-08-07-silent-zero-regression-screen-research` and the `W02.P02.S05` prior-art reading.
- Selected registry-build reachability (per binding-source-family probe) as the primary mechanism, layered with a build-time-enforced floor generalising the existing `implies_nonzero` verification-predicate mechanism from opt-in to mandatory-or-exempted for ledger-backed casillas.
- Rejected calculate-time prior-period comparison on its false-fire profile, citing both the general "routine business variation" argument and the `_relation_prefill.py` no-prior-filing-is-legitimately-blank authority read in S05 as a second, authoritative source of the same false-positive shape.
- Named the residual blind spot explicitly in the ADR body: neither chosen layer catches a binding that reaches real matching rows and aggregates them incorrectly.
- Set the ADR status to `accepted` (the decision was already agreed with the plan's author before this record; this document is the durable capture of that agreement, not a new proposal awaiting review).

## Outcome

`2026-08-07-calculation-chain-integrity-adr` carries the full decision: Considered options names all four candidates (including the prior-art-driven fourth option to generalise the modelo-130-relation-regression three-state contract) with catches/misses/cost/false-fire for each; Implementation describes the two additive layers; Rationale states the single-conceptual-model argument for choosing option 4 over inventing an unrelated mechanism; Consequences names the per-family authoring cost as real campaign-scale work and explicitly defers `W02.P03` (building the gate) to after this ADR's acceptance, per the plan's own gating instruction. Vault-checked scoped to the feature tag: clean (the two pre-existing warnings on the separate, still-empty `calculation-chain-integrity-research` document are out of this step's scope -- that document serves other waves).

## Verification

## Notes

This ADR's mere existence under the `calculation-chain-integrity` feature tag also unblocked `vaultspec-core vault add exec` for every step in the plan -- the exec-scaffold lifecycle gate is tag-exact (requires an ADR document under the same feature tag) and does not recognise a roll-up plan's `related:`-cited ADRs from other feature tags. Reported as a possible tooling gap separately; not fixed here.
