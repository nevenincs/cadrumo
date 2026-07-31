---
tags:
  - '#exec'
  - '#delivery-pipeline-audit'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:ba3522a83c659f33256d8eb07182bc6a26c044bb61e2e4a6ca18e77b45acbd41'
step_id: 'S02'
related:
  - "[[2026-07-25-delivery-pipeline-audit-plan]]"
---

# D1 trigger, delete pypi-upload.yml with its conformance test and its three PyPI Trusted Publishing registrations upon the first successful publish-release Gate 3 PyPI publication, blocked until that publication happens

## Scope

- `.github/workflows/pypi-upload.yml`
- `dev/packaging/tests/`

## Description

- Reconciled the row against the tree and found its subject already deleted.
- Confirmed commit `e9e5acceb9` removed the workflow together with its five conformance tests, and verified no reference to the retired lane survives in code, the two residual matches being ordinary prose about PyPI upload paths rather than the lane.
- Established that the deletion arrived by a different route than this row anticipated, and left the row open for the half that is genuinely outstanding.

## Outcome

Partially satisfied, and deliberately left open.

The code half is complete. The workflow and its conformance tests are gone from
the tree.

The trigger this row names never fired. The row made deletion conditional on the
first successful publication through the primary authority's third gate, and no
such publication has occurred. What happened instead is that the lane's premise
collapsed: it existed solely to deliver an owed version to the package index for
a release the operator subsequently abandoned, so there was nothing left for it
to deliver. Deleting it executed the charter's end state by a stronger route
than the one written here, and additionally removed the two-authorities-under-
one-opt-in hazard the governing decision names.

The third element of this row's scope, the three Trusted Publishing
registrations and their environments, lives in registry settings this worktree
does not contain and remains an operator action.

## Notes

Recorded rather than checked. Marking this row complete would assert that a
successful publication triggered the deletion, which is false, and would also
absorb the outstanding operator registration cleanup into a closed row. The
honest state is that the tree-side work is done by supersession while the
registry-side work is untouched, so the row stays open against the operator
half alone.
