---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d1efa7be928bee632c96b2b085b240a8a7c7c46afb79ab0241cf2a685af7f184'
step_id: 'S47'
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
     The S47 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Restore canonical formatting on the shared registry authority after concurrent capture work introduced mixed line endings, then rerun focused authority Ruff, format, and deadline ownership tests without changing behavior and ## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Restore canonical formatting on the shared registry authority after concurrent capture work introduced mixed line endings, then rerun focused authority Ruff, format, and deadline ownership tests without changing behavior

## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Reformat the canonical registry authority with the repository-owned Ruff formatter after concurrent authority-capture work introduced mixed line endings and overlong imports.
- Preserve every symbol, comment, and behavior while wrapping only the two affected imports.
- Re-run canonical deadline ownership and native-authority capture tests.
- Obtain an independent formatting-only architecture review.

## Outcome

Ruff check and format check pass. The focused registry authority, native-capture, deadline ownership, and projection suite passes 21 tests. Independent review approved with zero findings and confirmed the final diff is formatting-only: two imports wrapped, with symbol and comment identity preserved.

## Notes

The first review correctly rejected an unstable intermediate tree because a peer-owned substantive authority rewrite was still uncommitted and temporarily incomplete. Work stopped without reverting that peer work. After the rewrite landed, formatting was reapplied to the new canonical revision and the review was repeated successfully. `git diff --check` was clean; Git emitted only its informational CRLF-to-LF normalization warning.
