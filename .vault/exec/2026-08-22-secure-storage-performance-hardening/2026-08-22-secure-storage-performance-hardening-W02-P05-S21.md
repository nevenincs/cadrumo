---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:8719de7df00fd32adcd8f1c6858f1b71402989e5f414bd8664c089dd9c70de72'
step_id: 'S21'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-08-22-secure-storage-performance-hardening-plan placeholders are machine-filled by
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
     The Add facade parity, cycle, forbidden-import, and read-only-materialization gates and ## Scope

- `src/cadrumo/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add facade parity, cycle, forbidden-import, and read-only-materialization gates

## Scope

- `src/cadrumo/tests/`

## Description

- Add fresh-process workflow facade parity and canonical-owner checks.
- Add dynamic static/literal-import cycle detection across module-level compound bodies
  with adversarial relative, absolute, and dynamic edges.
- Add forbidden write-boundary import plants, isolated-parent filesystem equality,
  unloaded writer census, and a real materialization bite.

## Outcome

The workflow facade maps every public symbol to its canonical lazy owner, the live
workflow module graph is acyclic, and config/path reads leave the complete isolated
filesystem unchanged without loading write-side modules. Eight focused tests and Ruff
pass; independent review approved the gates.

## Notes

The new parity gate exposed and corrected several re-export-owner mappings. No harness or
external-client file was modified.
