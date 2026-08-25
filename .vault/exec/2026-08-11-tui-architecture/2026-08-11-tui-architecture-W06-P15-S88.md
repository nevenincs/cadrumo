---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:50f4285c1585b838876042a6649b8f2dc31dbec9aac9f3f769089df278445544'
step_id: 'S88'
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
     The S88 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Close every generated migration-manifest row with its replacement import or out-of-process proof and ## Scope

- `dev/import_hygiene_scan.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Close every generated migration-manifest row with its replacement import or out-of-process proof

## Scope

- `dev/import_hygiene_scan.py`

## Description

- Delete the historical 515-row migration manifest, accepted digest, disposition table, and legacy-edge authority.
- Replace exact-count acceptance with a live zero-remnant detector for retired files, imports, dotted references, slash and backslash paths, and unreadable sources.
- Scan the detector itself and exempt only its exact annotated canonical retired-package declaration.
- Add planted failures for recreated modules, imports, qualified references, repository paths, malformed sources, and a second detector-local reference.
- Modernize stale test prose and fixture paths rather than allowlisting them.

## Outcome

TUI migration closure is now a fail-closed live fixed point rather than a preserved inventory of deleted code. The current detector returns no findings, while every planted retired shape fails. No historical count, digest, disposition, allowlist, shim, re-export, or private bridge remains.

Independent review approved S88. The complete focused import-hygiene and migration suite passed 63 tests; Ruff, formatting, exact census, and diff checks are green.

## Notes

The detector recognizes its own one canonical declaration structurally; a second reference in the same source is intentionally reported. S104 consumes this zero-remnant result as migration evidence but does not claim the separate interface C1 exit receipt.
