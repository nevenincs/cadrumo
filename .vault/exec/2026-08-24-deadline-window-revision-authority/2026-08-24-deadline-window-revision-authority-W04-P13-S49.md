---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:395349e4a8e4c94f92681cb2be568269132a68f8169a7083bb2b310f39701e48'
step_id: 'S49'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S49 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Restore canonical formatting after the concurrent authority-reset fix landed unformatted on the registry authority and its native-capture proof, preserving reset linearization behavior and ## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Restore canonical formatting after the concurrent authority-reset fix landed unformatted on the registry authority and its native-capture proof, preserving reset linearization behavior

## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`

## Description

- Apply the repository-owned formatter after the concurrent authority-reset linearization landed.
- Preserve the reset barrier, authority generation, deadline projection, assertion operands, and AST symbol checks.
- Re-run native-capture, deadline projection, and ownership tests and obtain independent review.

## Outcome

Ruff check and format checks pass. The native-capture, canonical deadline projection, and deadline ownership suite passes 20 tests. Independent review approved with zero findings and confirmed reset linearization and deadline authority behavior are unchanged.

## Notes

The textual diff only wraps one membership assertion and one AST-comprehension condition in the native-capture proof. The authority file is status-marked solely by line-ending normalization and has no textual or word diff. Git reports an informational CRLF-to-LF warning.
