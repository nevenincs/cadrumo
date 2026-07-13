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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S55 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Update developer recipes, release URLs, companion paths, and rollback commands and ## Scope

- `justfile` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update developer recipes, release URLs, companion paths, and rollback commands

## Scope

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
