---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S12'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add structure-and-wiring tests for the conformance profile composer, asserting provenance fields and degraded-mode labelling, never author-invented numeric expectations

## Scope

- `src/cadrumo/application/registry/tests/test_conformance_profile.py`

## Description

- Add fifteen structure-and-wiring tests over the composer, all grounded in the
  real bundled registry tree or in `model_copy` mutations of records read out of
  it. No mock, stub, skip, or xfail appears in the module.
- Assert row coverage as a RELATION — one row per revision the loaded tree
  declares — rather than as today's count, so a new modelo, a new revision, or a
  retirement never reds the gate.
- Add an anti-vacuity floor (50 modelos / 60 revisions, well under the current
  73 / 90) that an empty tree or a collapsed fold cannot clear.
- Assert the governance provenance fields are present on every row and that the
  reviewer pairing is coherent in both directions.
- Assert degraded-mode labelling rides on the rows, not only the envelope, and
  that the three authority-dependent axes are absent there rather than defaulted.
- Add two mutation proofs that flip a named assertion, plus a refusal test
  proving a revision the composer cannot fully describe raises rather than
  vanishing from the census.

## Outcome

Suite green under both the isolated serial run and the repository's default
selector, so the module is genuinely selected rather than silently deselected:

```
uv run --no-sync pytest src/cadrumo/application/registry/tests/test_conformance_profile.py -p no:randomly -n0 -q --no-header
...............                                                          [100%]
15 passed in 10.90s
```

```
uv run --no-sync pytest src/cadrumo/application/registry/tests/test_conformance_profile.py -q --no-header
...............                                                          [100%]
15 passed in 13.92s
```

The whole registry application package stays green: `50 passed in 14.17s`.

The mutation proof was verified by mutating the PRODUCTION composer, not merely
by exercising it. Two independent mutations were applied at once — the
governance projection made to emit the fail-closed default unconditionally, and
the row coverage property made to return the grounding fold's value without
distinguishing an absent claim from a zero one — and each flipped exactly one
named assertion:

```
....FF.........                                                          [100%]
E   assert <RevisionReviewStatus.PENDING_REVIEW: 'pending_review'> is <RevisionReviewStatus.OPERATOR_REVIEWED: 'operator_reviewed'>
test_conformance_profile.py:193: assert PENDING_REVIEW is OPERATOR_REVIEWED
E   assert 0.0 is None
     +  where 0.0 = RevisionConformanceRow(modelo='303', revision='2023-y-siguientes', ...).independent_check_coverage
test_conformance_profile.py:263: assert 0.0 is None
FAILED test_governance_stamp_is_read_from_the_revision_not_defaulted
FAILED test_independent_check_coverage_distinguishes_absent_from_zero
2 failed, 13 passed in 10.53s
```

The second failure is the discriminating one: only the absence-versus-zero
assertion reds, because the collapsed property still returns the right number
for every revision that reconciles something. A test that merely proved the
property was reached would have stayed green through that mutation.

The composer was then restored from a copy taken before the probe, and
`git diff` against HEAD reported an empty diff, confirming a byte-identical
revert. The suite returned to `15 passed in 10.90s`.

Gates: `ruff check` and `ruff format` clean, `ty check` clean, and the
relative-imports gate silent.

## Notes

The mandatory semantic-discovery probe was WAIVED for this campaign by explicit
operator directive; the semantic index is broken and the service is stopped
under a hands-off order. Grounding came from whole-file reads plus targeted
content search.

`AuthorizationState` is exported from the access-gate subpackage facade, not
from the core top level, so the test imports it from there.

The three-way coverage test is the load-bearing one and is worth preserving
intact: it asserts that one modelo revision scores a positive fraction, that the
same revision stripped of its declared grounding scores a real `0.0`, and that
the same revision stripped of its reconciled set scores `None`. Collapsing any
two of those three outcomes is the defect the row model exists to prevent, and
the test is the only thing standing between that model and a later
simplification that would reintroduce it.

Two module-scoped fixtures compose the full bundled profile once each, validated
and degraded. The validated compose dominates the runtime; the authority's own
process-wide cache keeps repeat runs cheap.
