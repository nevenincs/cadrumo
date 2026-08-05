---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:1cd3d33a96735eb585c1d665e332013fdbdfb6f2a42a0a75ae303adecc8f3111'
step_id: 'S23'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Prove an ambiguous or incomplete invoice is excluded from all three domains WITH a visible advisory, never silently dropped and never silently folded

## Scope

- `src/cadrumo/application/aggregation/tests`

## Description

- Build one ledger transaction carrying a full professional-invoice substrate and drive it through the renta income, retenciones and IVA projections in a single scenario.
- Assert the three legs reconcile to one decomposition rather than each satisfying its own domain in isolation.
- Build the substrate-less twin crediting identical cash and assert neither domain answers it silently.
- Pin the measured two-directional harm as a regression.

## Outcome

Landed in commit `c8bec3fff9` (1 file, +380).

The invoice is an ordinary Spanish professional service: base 1000, IVA repercutido 210 at 21% (LIVA art. 90), retención 150 at 15% (RIRPF art. 95.1, withheld on the BASE), total 1210, cash 1060. The figures come from the invoice arithmetic and the two cited rates, never from what an aggregator returns - an expected value read off the engine agrees with the engine by construction and proves nothing. A first test asserts the four satisfy the canonical identity before anything consumes them, so the scenario cannot rest on four numbers somebody typed.

The substrate-less twin credits the SAME cash and differs only in the recorded invoice, which is exactly the pair of states a cash amount cannot tell apart. The two domains answer differently and both answers are deliberate: IVA EXCLUDES the row with a reason naming the missing fact, income KEEPS it and flags it through the grounding marker, because dropping it would under-declare by the whole 1060 rather than mis-measure it by 60. Neither is silent, and that is the invariant.

What is pinned is not that the ungrounded figures are right - they are knowingly wrong - but that the wrongness is announced. The harm is also pinned as a regression so a later change cannot quietly alter its size: income over-declared by 60 AND the 150 credit lost, about 210 against the taxpayer from one absent field.

Test evidence: the module 9 passed, 0 failed. Aggregation suite 587 passed.

## Notes

DIVERGENCE FROM THE STEP WORDING, deliberate. The Step says an ambiguous invoice is "excluded from all three domains". Income does NOT exclude it, and must not: the governing decision keeps the fallback because dropping an untagged income row under-declares by its whole value, which is strictly worse than mis-measuring it. The invariant the Step is really asserting - never silently dropped, never silently folded - is what the scenario pins, and the record states both halves so the difference is visible rather than papered over.

The scenario reuses the existing raw-row factory from the income aggregation support module rather than building its own, so it cannot drift from the sibling income tests on the shape of a ledger line while claiming to describe the same pipeline.

A gap this surfaced and did NOT close: the calculate-path ungrounded advisory names the income mis-measurement but says nothing about the dropped retención credit, which is the larger half of the harm (150 of the 210). The scenario asserts the loss; the operator-facing advisory does not yet mention it. Worth its own Step.
