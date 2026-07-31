---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:931bfff5a5bf2dba1b487f4bc9b148bc49691debfdeadc0ea78dd0f646858116'
step_id: 'S06'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Prove every destination step idempotent against its own prior success so a re-dispatch of the same cohort converges, using clobber or skip-existing semantics per destination, gate: uv run --no-sync pytest dev/release/tests dev/packaging/tests -q -k idempot passes over the helper functions, end-to-end re-dispatch convergence needs CI and is flagged non-local

## Scope

- `.github/workflows/publish-release.yml`
- `dev/packaging/marketplace_publish.py`
- `dev/release/tests/`

## Description

- Survey each destination write for whether a re-dispatch converges or fails.
- Make release creation recognise and re-upload over this cohort's own release.
- Make the index upload skip files a partial prior upload already landed.
- Exempt this cohort's own release from the identity guard, keyed on the commit.
- Split the exemption rule out of the network shell so it is provable.

## Outcome

Landed under the commit subject `feat(release): make every destination converge
on a re-dispatch`.

The survey found three channel pushes and the payload upload already converged;
two destinations did not. Release creation failed outright when the release
existed, and the index upload failed on the first already-present file.

Release creation now recognises the release this cohort itself made, identified
by the same source commit, and re-uploads its assets. A release on any other
commit remains a hard error.

The index upload skips already-present files. Six distributions go up and that
upload is not atomic, so a fault after the third leaves three published and
three not; without skipping, a re-dispatch dies on the first present file and
the remaining three can never land. It is the one destination where a
half-finished write cannot be undone, so converging is the only remedy
available.

A design tension surfaced and was resolved rather than worked around: the
identity guard would have refused the recovery path itself, since a re-dispatch
finds its own release and the guard reads that as a collision. The guard gained
an own-cohort exemption keyed on the source commit, never on the version, which
is what prevents it laundering a release belonging to anything else.

Gate: the release suite passes at one hundred and eighty-seven tests.

Anti-tautology proof: making the exemption ignore the commit, which is precisely
the laundering defect, reds two tests.

## Notes

A tautological test was written and discarded before commit. The first draft
re-implemented the exemption filter inside the test and asserted against the
copy, proving only that the copy worked; a second asserted against an empty
input and was trivially true. Both were deleted, and the rule was split out of
the network shell as a pure function so the real implementation is exercised
against real rows. The refactor was prompted by the bad test rather than the
other way round, which is the useful part to record.
