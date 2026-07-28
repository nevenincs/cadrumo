---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S129'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S129 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Remove evidence-link input and evidence-update output fields from ledger link and ## Scope

- `src/cadrumo/entrypoints/cli/_ledger_payloads.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove evidence-link input and evidence-update output fields from ledger link

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`

## Description

- Read the ledger link result schema in the named payload module and enumerate its declared fields.
- Confirm no evidence-link input field and no evidence-update output field rides on the link result.

## Outcome

The link result declares only link metadata: an operation, a bucket id, a transaction id, an invoice id, and an actor. Its docstring states the separation outright, recording that link establishes an invoice-only bidirectional relationship and that evidence assignment is a separate operation which never rides on this result.

The evidence-update result class still imported by the module belongs to the separate and live evidence update verb, which is a different surface from the link result this Step governs.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
