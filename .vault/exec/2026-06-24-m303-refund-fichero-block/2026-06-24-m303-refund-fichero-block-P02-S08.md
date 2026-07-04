---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S08'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m303-refund-fichero-block with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-06-24-m303-refund-fichero-block-plan placeholders are machine-filled by
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
     The Refuse a refund disposition with no refund-account on file with an instructive typed error on the Notice channel, never an empty or partial DID block and ## Scope

- `src/aeat/application/modelo/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Refuse a refund disposition with no refund-account on file with an instructive typed error on the Notice channel, never an empty or partial DID block

## Scope

- `src/aeat/application/modelo/_export.py`

## Description

- Refuse a refund-disposition export that has no refund account on file with the typed `ModeloRefundAccountMissingError`, raised inside the header composer before any bytes are written.
- Refuse rather than emit an empty or partial cuenta-devolucion (DID) block, since a fichero with an empty DID page files a devolucion AEAT cannot pay.
- Route the refusal through the typed error class carrying a translated message so it surfaces on the operator Notice channel.

## Outcome

- `ModeloRefundAccountMissingError` is defined and exported in `src/aeat/application/modelo/_action_errors.py` and raised from the M303 export path when a refund disposition carries no `iban`.
- `test_modelo_303_refund_account_missing_e2e.py` asserts end-to-end that a REDEME refund export with no account is refused with the typed error and writes no fichero (neither the draft nor the receipt). Passes at HEAD.

## Notes

- This record documents the verified landed state at HEAD; the refusal fires before any draft write, so no partial artifact is produced.
