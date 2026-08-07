---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:6d07537575c2eabfae13e02faca123ce0b03081e31fce2ba2352ca327d8c31a9'
step_id: 'S06'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---

# Author the decision record selecting registry-build reachability as primary with the implies-nonzero coverage floor layered, rejecting prior-period comparison on its false-fire profile

## Scope

- `.vault/adr/`

## Description

- Authored the decision body of `2026-08-07-silent-zero-regression-screen-adr` (Problem Statement through Consequences), grounded in `2026-08-07-silent-zero-regression-screen-research` and the `W02.P02.S05` prior-art reading.
- Selected registry-build reachability (per binding-source-family probe) as the primary mechanism, layered with a build-time-enforced floor generalising the existing `implies_nonzero` verification-predicate mechanism from opt-in to mandatory-or-exempted for ledger-backed casillas.
- Rejected calculate-time prior-period comparison on its false-fire profile, citing both the general "routine business variation" argument and the `_relation_prefill.py` no-prior-filing-is-legitimately-blank authority read in S05 as a second, authoritative source of the same false-positive shape.
- Named the residual blind spot explicitly in the ADR body: neither chosen layer catches a binding that reaches real matching rows and aggregates them incorrectly.
- Set the ADR status to `accepted` (the decision was already agreed with the plan's author before this record; this document is the durable capture of that agreement, not a new proposal awaiting review).
- Authored the ADR initially under this plan's own feature tag (`calculation-chain-integrity`), then moved it to `silent-zero-regression-screen` per plan-owner direction -- that is where its grounding research already lives, and splitting the pair across tags would fragment the thing the pipeline exists to keep together. Moved via `vault rename` + `vault set-frontmatter` (never a hand-edit): the file, its tags, and its `related:` list all now name `silent-zero-regression-screen`.

## Outcome

`2026-08-07-silent-zero-regression-screen-adr` carries the full decision: Considered options names all four candidates (including the prior-art-driven fourth option to generalise the modelo-130-relation-regression three-state contract) with catches/misses/cost/false-fire for each; Implementation describes the two additive layers; Rationale states the single-conceptual-model argument for choosing option 4 over inventing an unrelated mechanism; Consequences names the per-family authoring cost as real campaign-scale work and explicitly defers `W02.P03` (building the gate) to after this ADR's acceptance, per the plan's own gating instruction. Vault-checked clean under both the originating and the final feature tag.

## Verification

## Notes

This ADR's existence under a feature tag (any tag) unblocked `vaultspec-core vault add exec` for every step in `calculation-chain-integrity` -- confirmed by the plan owner as correct, deliberate gate behaviour, not a tooling gap: the earlier scaffold cited three ADRs from OTHER feature tags and had none of its own, and the tool's own creation-time warning ("feature has no ADR", "no research document") named exactly that before scaffolding proceeded anyway. No bug report filed, per plan-owner instruction.
