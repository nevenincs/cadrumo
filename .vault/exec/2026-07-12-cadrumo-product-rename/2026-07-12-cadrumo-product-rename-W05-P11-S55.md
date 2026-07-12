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
