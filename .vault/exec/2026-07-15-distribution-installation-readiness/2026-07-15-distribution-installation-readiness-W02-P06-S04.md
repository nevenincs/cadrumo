---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Define and validate the immutable cohort identity and digest contract

## Scope

- `dev/packaging/cohort_manifest.py`

## Description

- Define a strict persisted release-cohort model with one closed artifact taxonomy.
- Bind source revision, version, canonical artifact paths, byte sizes, and SHA-256
  digests into one stable content-derived cohort identifier.
- Record diagnostic build identity and a timezone-bearing creation timestamp
  without making either value change the content identity.
- Reject missing, duplicate, undeclared, mutated, escaping, drive-qualified,
  backslash, dot, and non-normalized artifact paths.
- Refuse replacement of an existing cohort authority.
- Exercise roundtrip, mutation, inventory, incompleteness, stable-identity, and
  portable-path behavior against real files.

## Outcome

- The manifest requires exactly 12 named members: six Python distributions, the
  Python sub-cohort manifest, Claude plugin, Claude marketplace, MCPB, Scoop
  manifest, and Homebrew formula.
- Every member carries one closed kind, unique normalized POSIX path, byte size,
  and SHA-256 digest. Loading re-enumerates the directory and rejects both
  undeclared and missing files before accepting the cohort.
- The cohort identifier is stable across artifact input order, creation time,
  and diagnostic builder variation while changing whenever source or artifact
  identity changes.
- The builder identity records the exact Python, UV, platform, architecture, and
  fully hashed PEP 517 build-constraint digest.
- Focused Ruff and type checks passed. All 11 real-file manifest tests passed.
- Formal review passed S04 with no remaining finding.

## Notes

- This step approves the manifest contract only. The real full-cohort build and
  repeat-build proof remain S03 and S05.
- S03 and S05 remain open because committed source does not yet expose the
  cohort-aware marketplace materialiser required by S25; unrelated uncommitted
  workspace changes were not captured.
