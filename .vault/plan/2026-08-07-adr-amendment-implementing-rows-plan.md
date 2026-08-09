---
tags:
  - '#plan'
  - '#adr-amendment-implementing-rows'
date: '2026-08-07'
modified: '2026-08-09'
body_hash: 'sha256:9e1d0fefcc4c46cd958b3ad39d5c700af82747df71bd710ac1da3cf100af6e61'
tier: L1
related:
  - '[[2026-06-09-modelo-iva-routing-carry-adr]]'
  - '[[2026-08-07-rate-box-evidence-assertion-adr]]'
  - '[[2026-08-07-recargo-equivalencia-source-of-truth-adr]]'
  - '[[2026-08-09-adr-amendment-implementing-rows-roll-up-authorization-research]]'
  - '[[2026-08-09-adr-amendment-implementing-rows-adr]]'
---

<!-- RETIRED: S01 -->

# `adr-amendment-implementing-rows` plan

## Description

Three ADR amendments landed on 2026-08-07 that explicitly rule on code without
being self-executing: `2026-06-09-modelo-iva-routing-carry-adr`'s AIC-routing
amendment, `2026-08-07-rate-box-evidence-assertion-adr`'s per-block
precondition amendment, and `2026-08-07-recargo-equivalencia-source-of-truth-adr`
(still `proposed`). Each said its implementation would be tracked as a
separate open row; none had a `.vault/plan` Step until this document. This
plan is the durable home for that tracking, surfaced by the 2026-08-07 ADR
corpus reconciliation audit.

S05 (the art. 161 recargo re-key) is a precondition for S04 and had already
landed (`d43bd3366a`) before this plan was scaffolded; it is recorded closed
rather than pending so the plan does not misstate finished work as open. S04
stays open and blocked until `recargo-equivalencia-source-of-truth-adr` is
accepted, per that record's own status.

## Steps

- [x] `S02` - Re-route Modelo 390's intra-community-acquisition categories from the inversion-del-sujeto-pasivo line to the dedicated AIC box ladders, per the 2026-08-06 amendment to modelo-iva-routing-carry-adr, and close its two cross-modelo residues (AIC base imponible reaching no official box on M390 or M303, and the AIC binding's rate_kinds omitting zero on both); `src/cadrumo/registry/aeat/modelos/390/`.
- [x] `S03` - Test each of the four unmodelled M390 regimen blocks for a rate-blind total before applying the two-layer rate-box shape, per the rate-box-evidence-assertion-adr amendment's precondition; `src/cadrumo/registry/aeat/modelos/390/`.
- [ ] `S04` - Land the recargo mismatch advisory comparing an operator-supplied recargo figure against the rate resolved for its applied rate and date, blocked until recargo-equivalencia-source-of-truth-adr is accepted; `src/cadrumo/application/aggregation/`.
- [x] `S05` - Re-key the art. 161 recargo lookup on applied_rate and on_date so it can hold the RD-ley transitional recargo tiers, precondition for the mismatch advisory above; `src/cadrumo/domain/iva/`.

## Parallelization

S02 and S03 are independent M390 registry changes and may run in parallel.
S04 is hard-blocked on S05 (closed) and on `recargo-equivalencia-source-of-truth-adr`
reaching `accepted`; it must not start before that ADR's status changes.

## Verification

The plan is complete when every Step is closed. S02 closes on a real-behavior
test asserting Modelo 390's AIC categories reach the dedicated box ladders
rather than the inversion-del-sujeto-pasivo line, plus tests covering the two
named residues (AIC base imponible reaching an official box on both M390 and
M303; the AIC binding admitting the `zero` rate with a mutation proof). S03
closes on a per-block rate-blind-total test for each of the four unmodelled
M390 regimen blocks, applying the two-layer shape only where the
precondition holds. S04 closes on the advisory firing exactly on a
recargo-rate mismatch, staying silent on an unmodelled window, and a
mutation flipping the comparison reddening the matching-row control. S05 is
already closed and verified by its own landed mutation-proof suite.
