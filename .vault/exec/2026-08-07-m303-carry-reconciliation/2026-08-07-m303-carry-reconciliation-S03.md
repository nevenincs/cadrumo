---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:5391f0007cd5d9b93929276458850cc55368427bb78c64d46f66a9c45f3a9f6f'
step_id: 'S03'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

# Replace the algebraically vacuous available equals posterior plus generated assertion on the resultado basis with an independent check

## Scope

- `src/cadrumo/domain/iva_compensation/tests/test_filed_derivation_disposition.py`

## Description

A decomposition assertion in the derivation's own disposition test was
algebraically vacuous on the resultado basis. There the derivation reads the
generated component back out of the policy's answer as available minus posterior,
so asserting that available equals posterior plus generated is a rearrangement of
that definition and cannot fail. Two of the four parametrisations proved
nothing.

## Outcome

The identity is kept where it discriminates, the generada basis, where the
generated credit is the filed input and the available carry is computed from it,
so the two are independent.

The resultado basis is held instead to the properties that do discriminate for
it: a generated credit is never negative, a refunded period reports exactly zero,
and a carried period with a negative resultado reports a strictly positive one
with an available carry above the posterior. A derivation that zeroed both
dispositions, or neither, fails one of these.

## Verification

Proven by mutation, delivered as an external pytest plugin that makes the
resultado-basis conversion ignore the disposition. The replacement reds under it
while the mutation output empirically confirms the vacuity claim: the
disposition-blind derivation returned an available carry of 650 with a generated
component of 250 against a posterior of 400, so the replaced assertion held
exactly while a refunded credit was being carried forward.

That is the vacuity demonstrated by measurement rather than argued from the
code.

## Notes

This was the review's lowest-severity item and conditional on touching the file.
It was taken because the fix's central claim is that the two fields are one
decomposition, so a vacuous test of that identity is the weakest possible support
for it.
