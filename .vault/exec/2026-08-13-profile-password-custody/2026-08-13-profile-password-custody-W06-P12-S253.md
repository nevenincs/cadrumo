---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:efbf6da59224991a2a53f2d6bfed8bd50180a310ecc85d3b915ca7d93a6b0b69'
step_id: 'S253'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S253 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Replace stale ledger-evidence and invoice output assumptions with stable authority-backed dynamic witnesses on ledger-evidence and manage-invoices and ## Scope

- `docs/_sequences/contracts/ledger-evidence/ and docs/_sequences/contracts/manage-invoices/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace stale ledger-evidence and invoice output assumptions with stable authority-backed dynamic witnesses on ledger-evidence and manage-invoices

## Scope

- `docs/_sequences/contracts/ledger-evidence/ and docs/_sequences/contracts/manage-invoices/`

## Description

- Trace evidence mutation, invoice catalogue projection, link, and Modelo 349 source authority with Vaultspec RAG and exact symbols.
- Replace generated-identity assumptions with captured evidence, invoice, transaction, and work-unit witnesses.
- Preserve independent assertions for invoice kind, totals, operation type, evidence linkage, and calculation lifecycle state.
- Regenerate only the ledger-evidence and manage-invoices page outputs through the sequence owner CLI.

## Outcome

Both pages now address the objects created in their own examples and verify that the returned projections retain those identities. The assertions remain semantically independent: they also check monetary totals, invoice direction, intra-community classification, evidence linkage, removal refusal, and the Modelo 349 calculation state without duplicating ledger or invoice projection logic.

## Notes

- Earlier concurrent commit `98f34aa7b01` had already converted the evidence attachment and removal examples to captured identity and target-specific refusal assertions; S253 retained and extended that work.
- Verification passed: both page golden and cumulative coherence checks; 16 focused ledger/invoice application tests; 61 parser/comparator tests; 349 documented-command conformance tests; scoped Ruff and ty.
- The broader catalogue CLI integration run passed 14 tests and exposed one unrelated localisation assertion that expects an English field token while the command emits the Spanish refusal envelope; no product behavior in S253 caused that mismatch.
