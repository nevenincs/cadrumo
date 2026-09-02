---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:7baee7110a4dd20e19d43bac3b79947a6a1313dd4ce42462524f983e5d4661c0'
step_id: 'S44'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Reconcile the packaging workflow family against the sibling shape

## Scope

- `.github/workflows/packaging-quick.yml`

## Changes

- `M` `.github/workflows/packaging-quick.yml`
- `M` `.github/workflows/packaging-smoke.yml`
- `M` `.github/workflows/ci-full.yml`
- `M` `dev/ci/tests/test_wall_advisory.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/ci/tests/ dev/packaging/tests/test_packaging_quick_workflow.py dev/packaging/tests/test_evidence_release_transport.py` -> `pass`

## Notes

Three workflows described a publication authority that no longer exists, pinning gate
contracts to `publish-release.yml`. No workflow now names a file absent from the tree,
checked across the whole family rather than the packaging group.

`ci-full` also carried project metanarration in two shapes forbidden in the codebase: a
note that it was formerly another filename, and two steps introduced as replacements for
numbered gates in a retired workflow. Both are gone; what each step asserts is unchanged.

A second red gate surfaced while verifying and was repaired rather than left. The wall
advisory's consumer-parity check named two files and read them directly, and one had
been deleted, so the check raised a missing-file error that reads as a threshold failure
and is not one. It now discovers declarations under `dev/` instead of naming them, and
counts what it read: a discovery check that finds no consumer is indistinguishable from
one where every consumer agrees, so finding nothing is now itself a failure. Teeth added
for a consumer that widens its own copy.

The family stays at sixteen workflows against the siblings' eight. The packaging and
acquisition lanes prove channels whose source is unresolved, so consolidating them
further waits on that decision.
