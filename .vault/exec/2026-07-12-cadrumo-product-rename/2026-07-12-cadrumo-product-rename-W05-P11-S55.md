---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S55'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update developer recipes, release URLs, companion paths, and rollback commands

## Scope

- `.vault/exec/2026-07-12-cadrumo-product-rename/2026-07-12-cadrumo-product-rename-W05-P11-S55.md`
- `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- `dev/release/readiness.py`
- `dev/release/tests/test_justfile_release_guidance.py`
- `dev/release/tests/test_readiness.py`
- `justfile`

## Description

- Preserve `aeat` as the workstation doctor command and correct the stale
  execution-record claim that it invoked `cadrumo`.
- Replace broad tag pushes with explicit final or rollback tag pushes in both
  platform recipe variants.
- Cover the root and both companion distributions in rollback yank guidance.
- Make release-apply guidance name all version authorities, both exact
  companion pins, lock regeneration, lock verification, and the fail-closed
  readiness rerun.
- Extend the production readiness gate and real rendered-recipe tests to reject
  companion version or exact-pin drift.

## Outcome

The developer recipe surface continues to invoke `aeat config check`. Release
guidance now pushes only `refs/tags/vX.Y.Z` or the explicit rollback marker,
names all three PyPI yank targets, and treats the root version, both companion
versions, manifest, import version, exact companion pins, and regenerated lock
as one release cohort. The readiness gate blocks version or pin drift.

## Notes

No publish, push, yank, tag, or rollback action was executed. Ruff, formatting,
and Ty passed. Thirty-four release and configuration tests passed, including
real `just --dry-run` subprocess coverage of `release-apply`,
`release-rollback`, and `doctor`. `just --list` and `just --summary` also parsed
successfully. Documentation, release runbooks, CI, and unrelated staged
marketplace work were excluded.

This evidence-only remediation cross-carries the pre-existing sanitizer removal
of scaffold comments from this record and corrects Scope to enumerate all six
paths delivered by `c2230d2b77`; it changes no implementation or plan state.
