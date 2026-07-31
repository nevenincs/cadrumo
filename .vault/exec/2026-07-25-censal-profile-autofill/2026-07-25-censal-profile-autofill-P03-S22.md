---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:f155486e308ad4f1297452022b4158b2fc40021f51aea8eac2b823bd55283de7'
step_id: 'S22'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Make the clear branch consult provenance as the value branch does, so a clear the app wrote cannot earn the protection reserved for an operator decision

## Scope

- `src/cadrumo/application/user_profile/_censo_sync.py`

## Description

- Sweep the tree for every machine-written clear before changing anything, using a syntax-tree pass rather than a text search.
- Establish that all three such sites are gated to namespaces the censal read cannot adopt, so the defect is latent rather than live.
- Probe what provenance a machine-written clear actually carries, finding it defaults to the operator's own token at every site.
- Make the clear branch read the same provenance field the value branch reads, rather than introducing a second notion of who wrote something.
- Pin both directions, since the previous behaviour was correct for an operator's clear and a one-sided test could be satisfied by removing the protection entirely.
- Prove the new case fails without the change by reverting the branch locally and watching it go red, then restoring.

## Outcome

One new case beside the existing cleared-path case, twenty-four in the file.

`uv run --no-sync pytest` over the censal sync and manager pull tests reported `41 passed in 13.57s`, measured against the committed validation service rather than a peer's in-flight copy. At the committed revision the censal sync file alone reported `24 passed in 7.60s`.

Both lanes were exercised on the censo verbs: `20 passed` across unit and integration together, rather than the unit selection alone which silently deselects the integration cases.

With the clear branch reverted to its unconditional form the new case failed and the sibling passed, which is the asymmetry the pair exists to hold.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` reported `All checks passed!`.

## Notes

The probe changed what the fix means, and the finding is worth more than the change. A machine-written clear carries the operator's own provenance token, because none of the three sites passes a source and the default is the manual one. So asking the clear branch who wrote a clear is necessary but not sufficient on its own: it would read an operator token on every machine clear that exists today. The branch is now symmetric with the value branch, which is right and costs nothing, but a genuinely machine-intended clear would also have to stamp itself as such for the check to bite.

Whether that is a defect is a judgement rather than an oversight. All three existing machine clears follow an operator action, a descendant removed or a divergence row superseded, so the operator token is arguably the honest answer for them. What does not exist yet is a clear the app writes with no operator intent behind it, which is exactly the case this branch now handles.

A peer's commit swept this Step's uncommitted test file into itself while the source change was still local. That left the committed tree carrying a case asserting behaviour the code did not implement, until the source change landed a few minutes later. Nothing was lost and the sweep was not careless; it is the ordinary consequence of a pathspec commit reading the working tree in a worktree where several agents edit adjacent files. It is recorded because the window it opens is a red tree that neither agent would recognise as theirs.

The measurement had to be taken against the committed validation service twice, because another campaign's enum enforcement sat uncommitted in the tree and refused a shared fixture. Their copy was set aside and restored byte-identically each time.
