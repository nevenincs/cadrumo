---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S29'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S29 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Remove the attach_evidence double full-catalogue decrypt by threading one decrypted catalogue through the command and ## Scope

- `src/aeat/application/ledger/_actions_manual.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove the attach_evidence double full-catalogue decrypt by threading one decrypted catalogue through the command

## Scope

- `src/aeat/application/ledger/_actions_manual.py`

## Description

- Add an internal `_preloaded_catalogue` param to `update_manual_transaction_fields`;
  when present it is used instead of `repository.load()`.
- `attach_manual_transaction_evidence` captures the catalogue it already loaded for
  validation and passes it through, eliminating the second full-catalogue decrypt.

## Outcome

A single `attach` no longer decrypts + parses the whole bucket transaction
catalogue twice. 304 ledger tests green. Committed in `b71c9e6fc`.

## Notes

The architectural fix (one secure-object row per transaction so single-row
mutations stop rewriting the whole catalogue) remains tracked as W06.P14.S31.
