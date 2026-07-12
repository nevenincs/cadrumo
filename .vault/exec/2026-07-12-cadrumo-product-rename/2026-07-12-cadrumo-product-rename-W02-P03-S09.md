---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S09'
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
     The S09 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Move the production package root without leaving an aeat import package and ## Scope

- `src/aeat to src/cadrumo package tree` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Move the production package root without leaving an aeat import package

## Scope

- `src/aeat to src/cadrumo package tree`

## Description

- Verified resolved source and target roots remained inside the workspace.
- Relocated the complete dirty `src/aeat` tree into `src/cadrumo` with native PowerShell moves.
- Preserved staged, modified, deleted, tracked, and untracked content while merging the existing identity core.
- Retained both core facade contracts in the relocated `core/__init__.py` without an alias package.

## Outcome

Moved the entire source tree to `src/cadrumo`; `src/aeat` no longer exists. The move carried 218 overlapping source changes recorded by the ownership ledger, all mechanically relocated tests, bundled data, and ignored runtime cache files. The existing `product_identity.py` remained byte-preserved. The sole source collision, `core/__init__.py`, was resolved by retaining the full relocated core facade and adding the four canonical identity re-exports.

Twenty-four ignored bytecode filename collisions were preserved with `.relocated-aeat` suffixes; they are not source or staged artifacts. No imports, dynamic strings, registry targets, or test semantics were rewritten in this Step.

## Notes

- The first merge pass moved all source content but PowerShell reported errors removing some newly emptied directories; a second bottom-up non-recursive cleanup removed them. One duplicate bytecode collision required a second unique suffix. No source file was lost.
