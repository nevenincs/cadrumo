---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:5cf9012080da45c9ee250c5aadcaab83917c5f3fc89ee1f377fe0792fa262120'
step_id: 'S21'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Feed the censal ownership refusal from the read itself rather than from a projected tuple named for adoption, so editing that tuple cannot disarm the guard

## Scope

- `src/cadrumo/application/user_profile/_censo_sync.py`

## Description

- Check first whether the identity-guard work in the auth module had already moved this, and confirm it did not, since that work touched a different file entirely.
- Take the fiscal identity as an argument to the reconciliation, sourced from the read itself.
- Stop projecting the identity, so the tuple carries the adoptable paths and nothing else.
- Remove the loop branch that skipped the identity, which is unreachable once it is not projected.
- Remove the now-dead candidate entry that fed the projection its identity value.
- Pass the read's identity from both callers, and simplify the operator-facing count that had been filtering the identity back out.
- Correct two docstrings that described the old arrangement, one claiming the identity is projected and one describing the session guard before it was widened.
- Re-exercise the cross-taxpayer refusal directly, since the guard's input path changed.

## Outcome

Two new cases and eleven updated call sites across the censal sync tests and the manager pull tests.

`uv run --no-sync pytest` over both files reported `40 passed in 16.71s`, measured against the committed validation service rather than a peer's in-flight copy.

A direct exploit probe confirmed all four behaviours through the changed input path: a foreign read refuses, an identity-less read refuses, a matching read adopts through case and surrounding whitespace, and a profile with no recorded identity still adopts a first read.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` reported `All checks passed!`.

## Notes

The hazard was that nothing would have failed. A collection named for adoption was silently load-bearing for an ownership refusal, so removing a path from it would have left the guard with no identity to compare and it would simply have stopped refusing. The failure mode of a refusal that stops refusing is that everything looks fine, which is why this needed dissolving rather than documenting.

The coupling was invisible from both vantage points, and that is the transferable part. An author editing the tuple reasons about what may be written to a profile. An author reading the guard sees a local variable. Neither view shows the dependency, and no test named it because the behaviour was correct in every state anyone had exercised.

Verification had to work around another campaign's in-flight change. An uncommitted enum enforcement in the validation service refused a shared test fixture that writes a placeholder into a required enum, so fifteen cases in the files under test were red for a reason unrelated to this work. Their cause was confirmed by reading the validation issue rather than inferred from proximity. To measure this Step honestly the peer's file was copied aside, the committed version put in place for the run, and the peer's copy restored byte-identically afterwards, which is the sanctioned way to compare against a committed version without destroying in-flight work.

That interference is worth recording on its own terms: an uncommitted constraint that changes what other people's tests do is indistinguishable from a defect in the tree, and the only way to tell them apart is to measure against the committed version deliberately.
