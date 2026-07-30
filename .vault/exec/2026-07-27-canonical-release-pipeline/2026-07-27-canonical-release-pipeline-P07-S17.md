---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S17'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Wire the Homebrew and Scoop generator tests into the full-CI lane as a dedicated explicit-path serial invocation of packaging/homebrew/tests and packaging/scoop/tests, honoring their serial marker with a single-worker run rather than excluding it, sized into ci-full deliberately because their real sdist and wheel builds cost minutes that the per-push budget cannot absorb, gate: uv run --no-sync pytest packaging/homebrew/tests packaging/scoop/tests -q -n0 -m serial passes locally at 14 of 14 and a lane conformance test pins the ci-full invocation covering both paths

## Scope

- `.github/workflows/ci-full.yml`
- `dev/ci/tests/`

## Description

- Add a dedicated explicit-path serial invocation to the dispatch-only full lane.
- Add the lane conformance test pinning the paths and the single-worker form.
- Prove the single-worker assertion by mutation.

## Outcome

Landed under the commit subject `ci(full): run the channel generator tests,
which no lane selected at all`.

The fourteen tests binding the generated formula and manifest to a real built
cohort were selected by nothing. The per-push lanes scope to the dev tree and
exclude the serial marker; the pathless invocations inherit configured test
paths that cannot reach the packaging tree; and the acquisition workflows invoke
the generators but never their tests. Two independent breakages accumulated
there unobserved as a result.

Explicit paths and a single worker are the contract rather than incidental
style. A marker-filtered parallel run holds serial tests out while still
reporting a clean pass, which is the same false green that hid the breakages, so
selecting them by marker alone would reinstate it.

Sized into the dispatch-only lane deliberately. These tests build real source and
binary distributions, costing minutes the per-push budget cannot absorb, and
that constraint is recorded beside the invocation so a later lane-sizing pass
does not silently undo it.

Gate: the declared command collects exactly fourteen tests, and the lane
conformance suite passes at thirty-one.

Anti-tautology proof: changing the single-worker flag to a parallel one reds the
conformance test with the message naming the reason.

## Notes

The plan asked for one Step and this became a phase of two, because lane
ownership and re-orphaning protection are separable deliverables: wiring these
particular tests into a lane does nothing to stop the next directory falling
outside every lane, which is the following Step.
