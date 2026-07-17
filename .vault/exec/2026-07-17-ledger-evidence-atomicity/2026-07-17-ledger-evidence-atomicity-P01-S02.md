---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S02'
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
     The S02 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Prove direct evidence patches fail, invoice linkage cannot mutate evidence, and failed attach or link leaves transaction, evidence catalogue, provenance, and event history unchanged and ## Scope

- `src/cadrumo/application/ledger/tests/test_actions_update_evidence.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove direct evidence patches fail, invoice linkage cannot mutate evidence, and failed attach or link leaves transaction, evidence catalogue, provenance, and event history unchanged

## Scope

- `src/cadrumo/application/ledger/tests/test_actions_update_evidence.py`

## Description

- Prove the generic command door refuses a direct evidence change (`update_manual_transaction` with an evidence-bearing command raises, names `aeat app ledger attach`, and leaves the row evidence-free with only the CREATED event).
- Prove the generic patch door refuses an evidence-field patch (`update_manual_transaction_fields`).
- Prove a non-evidence edit on an evidenced row succeeds and preserves the evidence verbatim.
- Prove `link_manual_transaction_invoice` does not mutate evidence: it links the invoice bidirectionally while leaving the transaction's evidence link and the bucket event history unchanged.
- Prove failed attach (unknown evidence id) leaves the transaction, provenance, and event history unchanged.
- Prove failed invoice link (unknown invoice id) leaves the transaction and event history unchanged.

## Outcome

- Real secure storage, real repositories, real bucket-event history; no mocks/stubs/monkeypatch. Every atomicity proof forces a refusal and asserts the on-disk state and event history are unchanged.
- `test_actions_update_evidence.py`: 7 passed. Full ledger application suite: 382 passed. Ruff clean. Commit `9296e3ebd2`.

## Notes

- The atomicity of a refused attach/link holds structurally: `_verify_evidence_references` and the invoice missing/cross-bucket guard both run before any `_save_transaction_catalogue_and_events` / catalogue write, so no partial write is reachable on the refusal path.
