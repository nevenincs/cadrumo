---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:38de3e682756e4dc64674b57f21fd0dc5ef69f68403caa37183069f93a3e9b0f'
step_id: 'S318'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S318 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Funnel the wizard save-exit notice through the shared output boundary, matching the sibling emitter in the same module that already does and ## Scope

- `src/cadrumo/application/wizard` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Funnel the wizard save-exit notice through the shared output boundary, matching the sibling emitter in the same module that already does

## Scope

- `src/cadrumo/application/wizard`

## Description

- Confirm the row's premise at HEAD before acting, since a peer had already funnelled the emitter.
- Consolidate rather than accept the redeclaration the funnelling introduced.
- Let the gate red first, and update its allow-list only after reading what it caught.

## Outcome

The save-and-exit disclosure now reaches the operator through the module's output boundary. **It already did when this row was picked up** — a peer had funnelled it — **but it had been given its own renderer call, its own sandbox-banner prepend and its own echo, duplicating the pair its sibling in the same module already held.**

That is the same redeclaration the streamed-progress fix made one package over: routing through the same renderer is not the same as sharing one implementation. **Two private copies of a boundary is precisely how one of these two emitters came to bypass it while the other did not** — the module had already run that experiment.

Both now delegate to one writer. The module holds one renderer call and one echo.

## Verification

    module renderer call sites      1
    module echo sites               1
    output-surface gate             6 passed
    lint and format                 clean

**The gate reddened before the allow-list was updated, on both of its properties at once** — flagging the new shared writer as an unowned emit site, and flagging both old exemptions as stale because neither function echoes any more. That is the second time in this session those rules have bitten on a real change rather than a synthetic control.

## Notes

**The allow-list shrank from two entries to one**, which is the structural result: the property is now enforced by there being a single writer rather than by two audited exceptions.

**One process defect, disclosed.** The first consolidation attempt removed the wrong import block — the new helper's own imports rather than the now-dead sibling ones — leaving four undefined names. The lint gate caught it immediately and it never reached a commit. The cause was a byte-level pattern matched against a file with mixed line endings, where the two candidate blocks differ only in their surrounding context.

