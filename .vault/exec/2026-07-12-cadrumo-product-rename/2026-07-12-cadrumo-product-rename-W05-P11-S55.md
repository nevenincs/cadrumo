---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S55'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update developer recipes, release URLs, companion paths, and rollback commands

## Scope

- `justfile`

## Description

- Retarget the workstation doctor recipe to the canonical Cadrumo executable.
- Verify release repository URLs, PyPI rollback guidance, and Cadrumo companion build paths.
- Classify retained AEAT recipe tokens as authority-facing live-capture and test taxonomy.

## Outcome

The developer recipe surface now invokes `cadrumo config check`. Existing
Cadrumo release-preview URLs, rollback instructions, publication diagnostics,
source paths, and both companion-project build paths were inspected and found
aligned with the committed product identity.

## Notes

The broad Cadrumo release and packaging recipe changes were already present in
the current committed file; this step preserved and verified those bytes and
changed only the remaining obsolete doctor command. No unrelated recipe WIP was
present when the scoped diff was taken.

`just --list`, `just --summary`, and dry runs of `doctor`, `release`,
`release-rollback`, and `publish-data` parsed successfully. Referenced Cadrumo
source and companion paths exist, and the scoped former-product residue gate
passed. `just --unstable --fmt --check` remains red because the repository
justfile differs wholesale from Just's unstable formatter; no bulk formatting
was applied. Formal review against the committed product-rename ADR found no
unresolved finding.
