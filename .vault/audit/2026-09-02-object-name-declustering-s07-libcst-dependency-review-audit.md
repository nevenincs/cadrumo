---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a3ba5c11c149679b2f918a6ea231ea6b3f4c0202af3d46af96bc4238706180ce'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `s07 libcst dependency review`

## Scope

Reviewed the direct LibCST development dependency added to `pyproject.toml` for
`W02.P04.S07` against the accepted ADR, implementation plan, and repository
dependency-group conventions. The review covered dependency placement,
production-install isolation, version policy, Python 3.13 availability, TOML
validity, resolver consistency, and the planned S07/S08 ownership split. No
dependency or lock file was edited by this review.

`libcst>=1.9.0` is declared once in the `dev` dependency group, leaving the
runtime and capability extras unchanged. The lower-bound form matches other
repository development tools, while the lock provides reproducibility. The
resolver selects LibCST 1.9.0 and records a CPython 3.13 Windows wheel, and the
installed development environment imports that exact version successfully.

## Findings

No findings.

The live `uv.lock` is already modified by concurrent `W02.P04.S08` work and
contains the resolved LibCST graph. This prevents a current-state assertion that
the lock remains untouched, but it does not broaden the S07 source change: the
reviewed declaration is confined to `pyproject.toml`, and lock ownership remains
the separate planned S08 step. Resolver checks found the concurrent lock
consistent with the declaration and requiring no further change.

## Recommendations

Retain LibCST as development-only transform infrastructure and preserve the
manifest, allowlist, and rehearsal boundaries required by the accepted ADR.
Land the lock refresh through `W02.P04.S08`, not as part of the S07 dependency
declaration record.

Validation passed: Python's standard TOML parser read the declaration,
`uv lock --check` succeeded, a dry resolver run reported no lock changes, LibCST 1.9.0
imported successfully, and `git diff --check` found no whitespace error. No
critical, high, medium, or low finding remains open for `W02.P04.S07`.
