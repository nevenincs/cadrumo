---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S01'
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
     The S01 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Make generic manual-field updates refuse all evidence fields, reserve evidence catalogue and provenance mutation for attach, and expose a single atomic invoice-only linkage writer and ## Scope

- `src/cadrumo/application/ledger/_actions_manual.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make generic manual-field updates refuse all evidence fields, reserve evidence catalogue and provenance mutation for attach, and expose a single atomic invoice-only linkage writer

## Scope

- `src/cadrumo/application/ledger/_actions_manual.py`

## Description

- Add module constant `_EVIDENCE_PATCH_FIELDS` naming `purchase_invoice_evidence_id` and `attachment_ids` as the reserved evidence axis.
- Add a private `_evidence_authority` keyword to `update_manual_transaction_fields` and `update_manual_transaction`; the patch door refuses when it sets an evidence field and the command door refuses when the replacement changes evidence, both directing the caller to `aeat app ledger attach`.
- Thread `_evidence_authority=True` from `attach_manual_transaction_evidence` (the sole evidence writer) through the delegation so attach still writes evidence.
- Add `link_manual_transaction_invoice`, a single atomic invoice-only linkage writer that resolves the transaction, enforces the invoice missing and cross-bucket policy before any catalogue write, then delegates the bidirectional link/persist to the invoices facade; it never touches evidence. Export it from the ledger package facade.
- Sweep the forced consumer changes: the CLI `ledger link --evidence-id` branch routes through attach; the LLM no-split classifier drops the redundant evidence patch (parent carry-forward preserves it); the LLM split-child evidence inheritance threads `_evidence_authority=True` (relocated to the atomic writer in P02).

## Outcome

- Evidence catalogue and provenance mutation is now reachable only through the attach authority; the generic patch and command doors refuse it.
- `link_manual_transaction_invoice` exposes the invoice-only writer P03 will route the CLI `ledger link` through.
- Files: `_actions_manual.py`, `__init__.py`, `_llm_classification.py`, `entrypoints/cli/_ledger.py`, plus consumer-sweep test updates in `test_actions_update_evidence.py` and `test_attach_purchase_evidence_store.py`.
- Verification: ledger application suite 375 passed; CLI link/check, ledger-modelo-staleness, catalogue-invoice-link, LLM evidence-split, and evidence-draft suites green; ruff clean; `--collect-only` clean. Commit `744c61adb8`.

## Notes

- The split-child evidence inheritance passing `_evidence_authority=True` through the generic door is an interim: P02.S04 moves that inheritance into the atomic split writer in `_actions_split_manual.py`, at which point the split path no longer touches the generic door.
- Comprehensive bypass-impossible and atomicity proofs (invoice linkage cannot mutate evidence; failed attach/link leaves catalogue, provenance, and event history unchanged) are S02/S03; S01 landed a baseline proof so the suite stays green.
