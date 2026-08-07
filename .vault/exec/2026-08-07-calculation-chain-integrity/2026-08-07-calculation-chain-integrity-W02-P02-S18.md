---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9e9ed0e43a02e77ca12dec4a6d2027d4febea276b3053021167b720ecc0a23b4'
step_id: 'S18'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W02.P02.S18

## Outcome

Read the relation-prefill zero-default authority before designing the screen, and established the false-positive floor it defines.

## The authority

`relation_prefill_period_zero_default_binding_ids`
(`application/calculations/_relation_prefill.py:909`) is the single answer to "which bindings are legitimately pre-satisfied with zero in this period". Its own docstring claims that role, and the claim holds: both consumers read it — the calculate resolver `_modelo_202_first_period_previous_payment_defaults` and the readiness missing-bindings projection (`application/state_projection.py:744`) — so readiness and calculate agree on the missing set by construction rather than by parallel reimplementation.

## What it actually admits, which is narrower than the Step implies

The set is **Modelo 202 only**, and within it a binding qualifies on three conjoined conditions: `source is RELATION_PREFILL`, at least one relation targets it, no targeting relation covers the requested period, and every targeting relation is `previous_period` sourcing the same modelo. A same-model previous-payment carry has no upstream filing before its first target period, so the resolver materialises the slot as zero rather than leaving it absent.

## The floor this sets for the screen

A binding resolving to zero is NOT evidence of a defect when it is in this set — that zero is a declared, law-grounded default rather than an unreached binding. Any screen that flags zero-valued bindings must subtract this set or it fires on M202's first period every year, which is the shape that trains an operator to ignore it.

The chosen mechanism sidesteps the floor entirely rather than subtracting it, and that is the stronger position. Registry-build reachability asks whether a selector *can* match any constructible shape, never what it resolved to for a taxpayer, so a legitimately-zero M202 carry is invisible to it: there is no value to misread. The floor therefore constrains the layered `implies_nonzero` coverage half, not the primary probe — which is worth stating, because it means the primary screen carries no false-positive debt from this authority at all.
