---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:8bdb47673c93c34fb2d5c60f3499cba72b92a141809913c6e012dfb6a19b455a'
step_id: 'S65'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Make a cohort built twice from one commit carry one identity

## Scope

- `dev/packaging/tests/test_release_cohort_integration.py`

## Changes

- `M` `dev/packaging/python_cohort.py`
- `M` `dev/packaging/tests/test_python_cohort.py`

## Notes

The cohort identifier was not a function of the commit. The command-spec probe
recorded the absolute filesystem location of every module it read -- fifteen
hundred paths carrying the build's own process id and a fresh unique directory
name -- and that reading was sealed into the attestation envelope, the manifest
and therefore the identifier. Two builds of one commit produced two identities
while ten of the eleven artifacts were byte-identical; only the manifest moved,
and inside it only the probe reading and the envelope derived from it.

The environment stamp was never the cause. The builder sets every one of those
variables itself before producing an artifact, which is why the artifact
digests always agreed. No stamp can reach a field that records where the build
happened to run.

So the identifier was reproducible only under a condition nothing enforced,
and the missing enforcement belonged to the builder rather than to its caller.
The probe reading is now expressed relative to the installed tree, in the same
form the wheel listing already uses, and a reading that escapes that tree is
refused by the parent rather than trusted from across a process boundary.

This also corrects an acceptance recorded earlier in this campaign. Two prior
pieces of work observed these same two fields diverging, classified them as
benign path dependence, and carried that classification into later briefs as
settled. It was the defect, seen twice and excused twice.

## Scope

- `dev/packaging/tests/test_release_cohort_integration.py`

## Changes
