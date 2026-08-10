---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:94bcc8cbf0dbade4798379674e25c12c30f9e2361bcf4bf450580be421fe816d'
step_id: 'S320'
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
     The S320 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Correct the overstated redaction rationale carried in the streamed-progress fix, which claims the funnel masks filesystem paths when it masks only embedded identifiers and ## Scope

- `src/cadrumo/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Correct the overstated redaction rationale carried in the streamed-progress fix, which claims the funnel masks filesystem paths when it masks only embedded identifiers

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Correct the claim where a reader of the code will meet it, since a commit body cannot be amended.
- State what the policy does and does not do, rather than deleting the sentence and leaving a gap.
- Own the error rather than attributing it to the worker who executed the change.

## Outcome

The commit that introduced the streamed-progress primitive described the leaked material as full local filesystem paths and called them exactly the material the funnel exists to mask. **Measured, the policy substitutes embedded tax identities and opaque record identifiers and leaves the surrounding path intact.**

The leak was real and the fix is correct. The rationale claimed a protection that does not exist, **in the direction that made the finding sound worse**, and it reached a commit message that outlives the conversation.

The primitive's docstring now states what is masked and what is not, and names the narrower true claim: identity and opaque-identifier masking on a channel that had none.

## Verification

    changed lines            9, all docstring prose
    executable lines changed 0
    lint                     clean

## Notes

**The failure was structural rather than careless, and saying so makes it transferable.** The probe output carrying the disconfirming evidence had already been read when the claim was written — the path was plainly visible surviving the substitution while the identity inside it was replaced. Reading past evidence one has already seen is the ordinary shape; carelessness is the rare one.

**It was caught by the executor of the change, not by its author**, on a review that was not looking for it.

**The correction lives in three places deliberately**: this record, the sibling record for the fix itself, and the module docstring. The vault is removable development scaffolding by its own rules, so a caveat that lives only there is one deletion away from a clean-looking history.

