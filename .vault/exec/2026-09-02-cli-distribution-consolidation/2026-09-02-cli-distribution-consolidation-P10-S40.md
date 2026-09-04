---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:c51db1d55660061f73b7b81e4135b8f0f9e564e3ec612639a9ef8684a34b184f'
step_id: 'S40'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove the evidence leak sweep left without a caller

## Scope

- `dev/packaging/evidence_leak_sweep.py`

## Changes

- `D` `dev/packaging/evidence_leak_sweep.py`
- `D` `dev/packaging/tests/test_evidence_leak_sweep.py`
- `verify:` `uv run --no-sync pytest -q -n0 --collect-only dev/packaging/` -> `pass`

## Notes

The sweep was held open because whether it was dead or merely dormant depended on how the
managed channels sourced their artifacts. That is now settled: both generators address
the index, no workflow attaches an asset to a release, and a standing gate forbids the
packaging workflows from reaching the releases API at all. The hazard it guarded - a
runner hostname or an operating-system username riding into an asset published on a
release - has no path to occur.

Deleting a security control needs the hazard gone rather than the control unreferenced,
which is why this waited on the channel decision rather than being counted as residue
alongside the other unreferenced modules.
