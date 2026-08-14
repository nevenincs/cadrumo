---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:373f9d4841dc453df6fa4d9040d86735dd089f918585f666bbec011c8418c99c'
step_id: 'S83'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Measure routine unit and dedicated harness runtime without nested outer xdist

## Scope

- `justfile`
- `dev/ci/lane_reachability.py`
- `dev/ci/tests/test_machine_aware_load.py`
- `dev/ci/tests/test_ci_workflow.py`
- `src/cadrumo/tests/test_lane_reachability.py`

## Description

- Measure which lanes actually collect the two harness proofs rather than reading the recipe shape.
- Declare the member paths once and derive both the enrolling runner and every lane exclusion from that declaration.
- Teach the lane authority to resolve justfile variables, failing closed when the renderer is absent.
- Give the lane record an exclusion field parsed from both spellings, and subtract exclusions in the coverage predicate.
- Delete the private justfile parsers in the two gate modules and consume the one authority.

## Outcome

Moving the proofs out of the unit lane had left them fully reachable from the parallel integration lane: both carry an integration marker, neither carries the serial marker, so that lane and its standalone variant collected all five cases into their own worker pool, and the dispatch-only full lane reaches the recipe on shared runners. Measured before: five tests collected. Measured after: five deselected, while the dedicated verdict still collects exactly five. The cost avoided is multiplicative rather than additive, because each proof spawns a child pytest, so an outer pool of width N yields N inner pools.

The exclusion is by explicit path, as the governing decision requires. Each member path is written once in the justfile and both the runner and the four lane exclusions derive from it, so the list cannot drift between the recipe that runs the members and the lanes that hold them out.

## Notes

Two wrong turns preceded the landed shape, both recorded because the reasoning matters more than the diff.

The first attempt introduced a capability marker carried alongside the execution marker. It was internally sound and its gate bit correctly under mutation, but the governing decision explicitly forbids selecting this lane by a runtime-cost marker competing with the execution and hexagonal taxonomies. It was reverted rather than argued into an amendment.

The second attempt honoured that constraint but restated the member list at four lanes beside the recipe declaring it. Collapsing it to one declaration was correct and stands, but it broke something no gate reported: the lane authority parses the justfile as text, an unresolved variable reference is not recognised as a path, and a path-less lane falls back to the configured testpaths. The enrolling recipe's three lanes moved from naming their two modules to claiming the whole source tree. Widening a lane can only make more tests appear reachable, so every existing assertion stayed green while the precision was lost. The fix belongs in the authority, which now resolves variables through the renderer's own evaluation and fails closed when it is unavailable.

A second defect was found in the same surface and predates this work: the lane record modelled no exclusion at all, in either spelling, so a lane reporting that it covers an explicitly excluded file was the pre-existing behaviour. Before exclusions existed anywhere it was accidentally harmless. Both are now fixed at the one authority, proven by mutation: with substitution disabled the parser reads an unresolved reference as a plausible-looking path, which is the silent-wrong-answer shape rather than an error.

The runtime comparison this Step names is recorded with the lane measurements in the verification phase. The dedicated verdict measures two minutes twenty-four seconds against a defective corpus boundary and four minutes thirty-two seconds against the corrected one, the difference being real first-party modules the earlier boundary never reached.
