---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S52'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# reconcile the registry revision diff test whose changed-formula expectation this campaign moved when it corrected the prorrata rounding on both M303 revisions, fixing whichever side is actually wrong rather than re-anchoring the test to make it pass

## Scope

- `src/cadrumo/application/registry/tests/test_diff.py`

## Description

- Diagnose the vanished changed-formula anchor against both revisions read through the registry authority and against the two commits this campaign landed on the prorrata percentage.
- Retire the prorrata anchor and re-anchor the devengada total on its coupling to a casilla the same diff reports as added, so the assertion reads the structural reason rather than restating an identifier.
- Anchor the resultado formula on the two dated ordenes that approve the two form versions.
- Add the missing set-level claim that a changed formula appears in neither the added nor the removed list and genuinely differs when the revisions are read off the authority.
- Add the missing silence half, anchored on the now-identical prorrata formula and its legally unamended articles.
- Add a Modelo 180 witness isolating the legal-grounding dimension, which no assertion covered.
- Record in the module that no revision pair diverges in rounding alone, so that dimension is stated as unproven rather than implied covered.

## Outcome

The anchor legitimately vanished and the test was the wrong side. The prorrata percentage never differed for a rulebook reason: the older revision's no-volume-data branch returned 0 where the newer returned 100, which zeroed a fully-taxable trader's deduction, and the correction landed on the grounding that the applicable articles are unamended across both revision windows. The rounding correction moved both revisions identically from the shared half-up code to the ceiling code and never changed the diff at all. The two formulas are now byte-identical in expression, legal refs and rounding, which is what the law requires, so the expectation had been pinning the defect in place.

The anchor was arbitrary as well as wrong. Its only tracked difference was expression, a dimension the surviving devengada anchor already covered, and it was selected the way the whole module was: by reading the tool's own output back as ground truth.

Six mutations of the diff machinery were measured through a meta-path redirect to a scratch copy, so no mutant was ever written into the shared worktree, each run in a subprocess at zero workers because the default options carry automatic distribution and workers would re-import the real module. An identity-control overlay reproduced `13 passed` before any verdict was trusted, and the harness aborts unless the imported module resolves inside the overlay.

Dropping the expression comparison removes the devengada total from the changed set and fails exactly one test. Dropping the legal-grounding comparison empties the Modelo 180 changed set and fails exactly one test, the new witness. Reporting every common formula as changed fails two, the set-level classification claim and the silence half. Misclassifying changed formulas into the added list leaves the changed set completely unchanged and is caught only by the new disjointness claim, a dimension nothing covered before. The clean run is `13 passed`, the owning package is `56 passed in 23.90s` exit 0, and all thirteen collect under the default selector.

## Notes

Semantic-search discovery was explicitly waived by the operator for this Step: the semantic index is broken and its service stopped, so the service was neither started nor queried. Grounding was whole-file reads of the diff implementation and its test, direct probes of both revision pairs through the registry authority, and the history of the two commits that moved the formula.

The rounding dimension of the formula comparison remains unproven and is deferred, not closed. A registry-wide sweep of every modelo carrying two or more revisions found two formulas differing in expression alone and two differing in legal refs alone, and none differing in rounding alone, so no witness exists in the bundled data. Dropping that comparison produces no behavioural delta and reds nothing. The gap is stated in the module rather than papered over; closing it by authoring a rounding divergence into a revision would be inventing a rulebook change to satisfy a test, which the grounding rules forbid. It closes for free the first time a real revision pair diverges in rounding alone.

The two revisions share only nine formulas, so the changed set is small and every anchor in it is load-bearing. The set-level claims were written to hold across future registry evolution: a new legitimate divergence satisfies them rather than reopening this Step.
