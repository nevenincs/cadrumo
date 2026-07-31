---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:66ea78ff827458c62fcdda6aff360acb0e740df01353b93e16e84bfecb64b490'
step_id: 'S210'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Resolve every in-scope blocker or major finding through its owning implementation Step

## Scope

- `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`

## Description

- Enumerate the findings the formal review produced and classify each by
  severity and owner.
- Give the one major-class finding an owning implementation Step rather than
  closing it in prose.

## Outcome

SATISFIED. One major-class finding, zero blockers, and the major now has an
owning Step.

The review produced exactly one finding above minor: the false-green class is
systemic. 246 corpus-scanning emptiness assertions tree-wide, 87 inside this
campaign's surface, assert an offender list is empty without asserting that
anything was scanned. It has an owning Step now - the floor-or-prove row added
to this Phase - rather than a recommendation in an audit that nobody is
accountable for.

Resolving it by TRACKING rather than by fixing is a deliberate call, and the
reasoning is on the record. The finding is LATENT, not active: the
representative gate read in full walks 1733 real files, so its assertion is
meaningful today. What makes it a defect is that a path rename or package
relocation silently empties the corpus and the gate stays green while the
condition it forbids survives - which is how all five previously-confirmed
instances arose. A latent class with a bounded mechanical remedy is exactly
what a tracked Step is for; editing 87 test files across peer-owned surfaces at
94 percent campaign completion is how a close turns into a new campaign.

Zero blockers. The campaign's own gates were checked separately and each
carries a floor, three of four mutation-checked when they landed, so the
campaign did not add to the class it was eradicating.

The two remaining honest residues are not review findings and are not resolved
here, because neither is in scope for this row: the semantic index is dead and
its sweep row stays open, and six keychain-marked custody cases remain
unverifiable under an agent logon.

Gates at HEAD `e34a33420fd60fba08686f2e5417962a8b3f8938`:

- `uv run --no-sync vaultspec-core vault plan step add` created the owning row
  at canonical id `W06.P20.S297`, exit code 0.
- The finding's measurement: 16331 test functions scanned, 246 candidates
  tree-wide, 87 in-surface, representative gate corpus 1733 files.

## Notes

Recorded because the distinction governs the closure. A finding resolved by
tracking is resolved only if the tracking is real - a Step with an action, a
scope and an open checkbox that a later reader can execute. A finding
"resolved" by a recommendation paragraph in an audit is not resolved at all,
and this campaign's own history includes recommendations that sat unactioned
until a close review turned them into Steps.
