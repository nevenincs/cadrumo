---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S09'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden file-at-aeat.md and ## Scope

- `docs/how-to/file-at-aeat.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden file-at-aeat.md

## Scope

- `docs/how-to/file-at-aeat.md`

## Description

- Verify-close: read `file-at-aeat.md` in full against the hardening standard and confirm its audit findings are resolved at HEAD.
- Confirm the audit's own positive confirmation for this page: the never-submit safety boundary is stated correctly, and every cited in-tool command (`work revision`, `modelo export`, `work file --notes/--by`, `reconcile file`, `reconcile pull`) exists, takes the documented flags, and refuses cleanly for unverified drafts or missing markers.
- Confirm the ordered upload checklist correctly places the manual AEAT-portal step outside the tool and records the local `work file` marker only after portal submission.

## Outcome

- Page verified compliant at HEAD; the audit records `file-at-aeat` SAFETY as solid with all cited commands valid. Delta: none required.
- Imperative ordered checklist, prominent never-submit boundary, checksum-record guidance, cross-links resolve.

## Notes

- Residual m16 (invalid-PDF parser-internals leak on `reconcile`/`file-at-aeat`) is an APP-side typed-refusal finding, out of documentation-hardening scope. CLI conformance gate green.
