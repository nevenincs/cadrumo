---
tags:
  - '#exec'
  - '#code-dedup-sweep'
date: '2026-07-25'
modified: '2026-07-26'
step_id: 'S04'
related:
  - "[[2026-07-25-code-dedup-sweep-plan]]"
---

# Extend the lineage gate to pin the two facts the vacuity proof rests on, asserting each registered namespace's declared schema_version against the version its readers compare and the Envelope ge=1 floor, expressed as a relation rather than the literal 1 so a legitimate per-namespace bump does not red it

## Scope

- `src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py`

## Description

Pin the two structural facts the inner-envelope equality argument depends on, so
the proven no-op cannot silently become a real refusal against filed taxpayer
data. The ruling required these expressed as a relation rather than against the
literal 1, because the inventory does not rest on one shared constant: 66
namespaces declare the shared secure-object constant and a 67th declares its own
blob-manifest constant, so the proof holds today on a coincidence of value.

## Outcome

Landed in commit `cd64d40215` as a dedicated module in the storage tests package.

It pins that the envelope's `schema_version` carries a positive lower bound, and
that the bound reaches the lowest version any registered namespace declares. Both
as relations, so a legitimate per-namespace version bump does not red them for
the wrong reason.

**The first draft of the second assertion was a tautology, and catching it is the
substance of this step.** Stated as "no registered namespace declares a version
below the envelope bound" it cannot fail: the namespace definition's own
`schema_version` field carries `ge=1`, so with the bound at 1 the comparison is
unsatisfiable by construction and would have reported green forever while proving
nothing. It was replaced before committing with the direction that can genuinely
regress — the bound being loosened out from under the inventory. Shipping the
first form would have added another gate that cannot see the thing it guards,
which is this campaign's own critical finding.

Two proofs guard the guard: the bound is read from the model with a helper that
raises rather than defaulting, so deleting the real constraint fails loudly
instead of reporting a healthy floor; and the reach relation is driven against a
deliberately loosened stand-in to demonstrate that it breaks.

The ADR's numbers were re-verified empirically at HEAD rather than carried from
the record: 67 registered namespaces, all at version 1, and the envelope field's
metadata is `[Ge(ge=1)]`. The record's count of 66 was one short, as the ruling's
Correction 1 stated.

## Notes

S01 through S03 were delivered by peer agents while this step was being written,
and were verified rather than assumed: the predicate exists and is exported from
the storage facade, 41 call sites route through it, the twenty loose comparisons
are gone, and the only four remaining ordering comparisons in production are
exactly the set the ruling placed out of scope — layer one's ceiling, a SQL
constraint string, and the two correctly-paired two-sided gates on the archive
and encrypted-bundle tiers.

The sweep honoured the hardest constraint in the ruling. `usage_ratios` keeps its
own raise inside the `try` whose `except` re-raises a different error type, so the
non-raising predicate preserved that site's except-clause ordering — the specific
hazard that defeated the naive consolidation.

A red on `test_namespace_registry` during verification was attributed before
being believed, and was not this step's: a peer was mid-edit adding a namespace
and bumping the test's hardcoded count, and the module passed on its own. It is
also the visible edge of that peer executing S01 of the reconcile-evidence
relocation plan.
