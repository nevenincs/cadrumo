---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ca99e5ce719725be58bbf571a998b7e545905e71f0248df7d843fddf624d17dc'
step_id: 'S02'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

# Route the local filing path refunded rewrite through the canonical derivation and drop the contradicted formula provenance to match the sede path

## Scope

- `src/cadrumo/application/modelo/_filed_revision_observation.py src/cadrumo/application/modelo/tests`

## Description

The live local filing path encoded the refunded rule by hand beside the
derivation that owns it, so a regulatory change would land in one place and not
the other. It also rewrote only the value, leaving the formula id, the operand
refs and the operand values describing the 87-plus-generada addition that the
posterior-only figure contradicts.

The AEAT-capture sibling does the deliberate opposite and refuses outright when
supplied refs disagree with the formula's projection, so one case had two
incompatible answers and the local path persisted a provenance claim its own
value denied, all the way to the operator surface.

## Outcome

Both figures now come from the canonical derivation. The two selectors it reads
are supplied explicitly, each defaulting to zero when the filed revision declared
no such row, which preserves the previously verified reading that an undeclared
box 87 means there is no posterior credit to survive the refund. A complete input
cannot yield no answer, and the impossible case refuses rather than falling
through to a silent full-credit carry, which is the direction that over-states an
operator's available compensation.

The rewritten rows drop their formula lineage: formula id, operator label,
operand refs, operand casilla refs and operand values. Legal refs and source refs
are preserved on every row, because those answer why the casilla exists and must
survive to the operator surface; only the formula trace is untrue for a refunded
period.

No arithmetic was changed. The identity between the available carry and the sum of
its posterior and generated components holds after the rewrite, and a test asserts
it.

## Verification

Seven tests exercise the real rewrite and the real domain derivation, with
nothing stubbed. They assert the provenance shape, the preservation of regulatory
grounding, that untouched rows are carried through unchanged, that the local path
lands on the shape the canonical derivation dictates, and that the decomposition
survives.

No figure is manufactured as a parity expectation. What is asserted is provenance
shape and the decomposition identity, both contracts rather than AEAT arithmetic.

Proven by mutation, delivered as an external pytest plugin that restores the
pre-fix value-only rewrite. Four of the seven tests red under it, precisely the
provenance assertions. The three that still pass are the invariants the old code
also satisfied, which is the honest result rather than a weakness.

## Notes

The unreachable refusal is deliberate. It carries a plain message rather than a
localised one because it cannot fire for any operator input, and the alternative
was a silent fallthrough in the over-stating direction.
