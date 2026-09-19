---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c22dab8dfcdfde81a0212eea3ba01fcd52a5b8304aa4e71cdff0855a0bf1eb69'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `s08 libcst lock review`

## Scope

Reviewed the `uv.lock` delta for `W02.P04.S08` against the accepted plan and the
current direct development declaration `libcst>=1.9.0` in `pyproject.toml`. The
review covered project dependency metadata, selected versions, environment
markers, source archives and wheels, transitive additions, resolver
reproducibility, local importability, and unrelated lock churn. No lock or
dependency file was edited.

The delta adds the direct `dev` group edge and its `>=1.9.0` requirement, LibCST
1.9.0, and the conditional `pyyaml-ft` 8.0.0 dependency required below Python
3.14. Existing PyYAML satisfies LibCST on Python 3.14 and later. The package
record includes CPython 3.13 Windows artifacts used by this repository's local
runtime. No existing package record or version changed; the diff contains 73
additions and no deletion.

## Findings

No findings.

The resolver reports 255 consistent packages and a dry run requires no lockfile
change. The resolved local LibCST tree contains only `pyyaml-ft` on the active
Python runtime, matching the lock marker, and importing LibCST reports version
1.9.0. Direct TOML inspection confirmed the LibCST and `pyyaml-ft` package
records and dependency edges.

## Recommendations

Retain this resolver-produced lock delta with the S07 direct dependency. Future
changes to the LibCST lower bound should be followed by the same lock consistency
and platform-artifact checks.

Validation passed: `uv lock --check`, dry resolution, focused dependency-tree
rendering, local LibCST import, direct lock-structure assertions, and
`git diff --check`. No critical, high, medium, or low finding remains open for
`W02.P04.S08`.
