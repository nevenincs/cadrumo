---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7b38f6b25950c272a6d48249d73f13259121046ae89ec5b7e52fc3bc2c4bac1c'
step_id: 'S89'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S89 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Delete the legacy inbound TUI implementation and tests without a compatibility facade and ## Scope

- `src/cadrumo/adapters/inbound/tui` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the legacy inbound TUI implementation and tests without a compatibility facade

## Scope

- `src/cadrumo/adapters/inbound/tui`

## Description

- Delete the retired inbound TUI implementation, package root, and tests rather than preserving a compatibility surface.
- Move presentation tests to their canonical TUI owners before deleting their former files.
- Prove the retired package is absent from the filesystem, Git index, HEAD tree, import resolution, and live source references.

## Outcome

The retired inbound TUI package has no physical, tracked, importable, or referential presence. Canonical presentation tests live under `entrypoints.tui`; no shim, alias, re-export, or compatibility initializer remains.

The zero-remnant detector returns an empty result, the complete 63-test migration/import-hygiene gate passes, and independent review approved the deletion evidence.

## Notes

Implementation deletion landed in `ebeb4507a3`; final test relocation and deletion landed in `0acec93b1a0`. S88 owns the durable live-tree detector that prevents recurrence.
