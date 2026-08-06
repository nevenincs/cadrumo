---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:810b2652e2810a1bfa21989e0bfc97dada173c8cfb159c872f25cd043bc0bd2d'
step_id: 'S07'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Derive the prorrata from marital status, spouse record, and declaration type when no explicit per-descendant answer exists, and raise a non-blocking advisory naming the descendant and the inference

## Scope

- `src/cadrumo/application/modelo/_profile_binding.py`
- `src/cadrumo/domain/contribuyente/family.py`

## Description

## Outcome

Where no explicit per-descendant answer exists, the engine derives whether a second entitled
filer is indicated from profile signals already on record and applies the proration when they
indicate one, raising a non-blocking advisory naming the inference so the operator can confirm
or correct before filing. An explicit answer always wins over the derivation.

The default direction was preserved as the ADR requires. The executor confirmed explicitly
that it did not reverse it, which was the instruction: where signals indicate a second
entitled filer the engine prorates rather than granting the full amount, erring toward a
visible under-claim the advisory surfaces rather than a silent over-claim.

The advisory collector is wired into the calculation diagnostics coordinator and unit-tested.

Three limitations the executor named rather than left to discovery, all recorded as residuals
for the closing audit.

The derivation is not year-scoped. It reads the profile's current marital status and
declaration type regardless of which filing year is being computed, so a filer whose
circumstances changed inside the served window may receive the wrong inference for an earlier
year. The advisory surfaces the inference, which bounds the harm, but the limitation is real
and is the natural place a future effective-dating campaign would attach.

No end-to-end test proves the advisory reaches an operator through a real command invocation.
The collector is unit-tested and wired, but the operator-facing surface was not driven.

The new flag keys have no interactive-flow counterpart yet, so an operator using the guided
flow cannot enter these facts until the entry-surface Step lands. The flags round-trip and are
tested.

## Notes
