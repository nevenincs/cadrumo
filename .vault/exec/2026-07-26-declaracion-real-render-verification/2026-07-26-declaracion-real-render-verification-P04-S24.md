---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:cd655e44369bb66383994ae7bd3ece9bc5ad673c6c140a4a8c3b0ef7291c5c3b'
step_id: 'S24'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Correct the seven decl.ejercicio targets declared value_kind amount on what is a tax year, a schema mis-declaration rather than a guard gap

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

## Description

- Flip the seven decl.ejercicio targets from value_kind amount to text.
- Update the test assertions that read the extracted value as a Decimal.
- Verify the change is contained rather than a typed-boundary change.

## Outcome

Landed. Seven targets flipped across seven profiles, with the six test modules carrying the assertions updated alongside. Green across the declaracion suite, the calculations, filing and modelo suites, and the registry suite run sequentially.

The containment claim was re-traced rather than inherited. The single production reference is a docstring governing the filing builder's inputs, where a year casilla is supplied as a plain integer -- a different surface from extraction. Everything else reading the extracted entry is a test.

What the change buys is coherence rather than safety. All seven casillas are required, so a blank ejercicio means a malformed document rather than a legitimate blank, and the fabrication hazard the blank-box guard exists to prevent is close to theoretical for them. That was stated plainly rather than dressed up as a defect fix.

## Notes

The justification given at the time was wrong in a way worth recording. The change was described as closing the last incoherence in the estate, on a measurement of 281 targets of which exactly seven disagreed with their casilla's data_type.

An independent sweep found that the seven surface only under a rule distinguishing year from integer, a discrimination the original probe made silently. Swept naively the answer is four, and those four are different rows entirely: enum over text or integer, unadjudicated rather than fixed because the schema enforces no enum-versus-text distinction. They are tracked separately.

So the count was rule-dependent and the completeness claim riding on it was unsupported. The consequence beyond arithmetic is that the claimed payoff -- a gate asserting this invariant without an exemption list -- does not follow, because a gate written against the naive rule would miss the seven and flag four nobody has ruled on.

This record exists because a corpus consistency sweep found the Step checked with no execution record at all. That is the plan-closure discipline catching its own coordinator.
