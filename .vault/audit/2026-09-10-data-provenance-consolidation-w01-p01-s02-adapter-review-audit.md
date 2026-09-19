---
tags:
  - '#audit'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:141dae8bde35082c5c0634181b584cdee1c2603955a8f92f77883530bab9710d'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# `data-provenance-consolidation` audit: `w01 p01 s02 adapter review`

## Scope

Review the catalog adapters and their bundled-path identity boundary after implementation of W01.P01.S02.

## Findings

### path-alias-normalization | high | Raw path aliases could collapse to one catalog identity

The initial adapter normalized repeated separators, dot segments, and trailing slashes before validation. The implementation now rejects any raw spelling that differs from its canonical POSIX representation; focused probes cover the malformed variants.

### corpus-root-identity | high | The catalog admitted the corpus root as an artifact target

The initial validation accepted `.` because it has no path parts. The implementation now rejects an empty part sequence, and the focused probe confirms that root, traversal, aliases, and canonical paths are distinguished correctly.

## Recommendations

Keep all future catalog compilers on the same raw-path validation boundary rather than normalizing paths before identity construction.
