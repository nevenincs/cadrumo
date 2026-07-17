---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Prove create-time and attach-time evidence validation enforce the same missing and cross-bucket policy and ## Scope

- `src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove create-time and attach-time evidence validation enforce the same missing and cross-bucket policy

## Scope

- `src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py`

## Description

- Add the attach-side parity tests mirroring the four existing create-time refusals: missing purchase evidence, cross-bucket purchase evidence, missing attachment manifest, and cross-bucket attachment.
- Each attach test seeds an evidence-free transaction, then asserts `attach_manual_transaction_evidence` refuses the same invalid input with the same error substring create rejects, and leaves the row's evidence link empty.

## Outcome

- Demonstrates create and attach share one validator (`_verify_evidence_references`): neither door is a weaker route into the evidence catalogue. Missing evidence names `purchase_invoice_evidence_id` / `attachment_ids`; cross-bucket evidence names the `command bucket`.
- `test_actions_create_evidence_validation.py`: 8 passed (4 create + 4 attach). Full ledger application suite: 382 passed. Ruff clean. Commit `0ea2800b8c`.

## Notes

- Real InvoiceCatalogue and AttachmentStore over the shared secure-object store; cross-bucket cases seed a genuine other-bucket record and prove the bucket guard fires.
