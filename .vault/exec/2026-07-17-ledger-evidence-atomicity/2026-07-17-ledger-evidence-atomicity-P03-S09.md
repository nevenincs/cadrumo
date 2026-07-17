---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S09'
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
     The S09 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Prove attach remains the sole evidence mutation, invoice link is atomic and invoice-only, and link rejects every removed evidence grammar and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove attach remains the sole evidence mutation, invoice link is atomic and invoice-only, and link rejects every removed evidence grammar

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`

## Description

- Add `test_link_rejects_removed_evidence_id_grammar` (passing `--evidence-id` is an unknown-option refusal) and `test_link_requires_invoice_id` (a bare `link <tx>` refuses because `--invoice-id` is now required).
- Retarget `test_link_refuses_unknown_transaction_id` off the removed `--evidence-id` onto `--invoice-id`.
- Retain the instructive invoice-not-found proof (`test_link_refuses_operator_invoice_add_id_instructively`) proving a slim `invoice add` id is refused with the typed message routing to the evidence path.

## Outcome

- Proves `ledger link` is invoice-only, rejects every removed evidence grammar, and that attach remains the sole evidence mutation door (the generic-patch refusal is the S02 application-level proof). `test_ledger_link_check_verbs.py`: 11 passed (integration). Commit `aa99b74e47`.

## Notes

- Real Typer runner against an isolated profile-storage backend; no mocks.
