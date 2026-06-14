---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S30'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S30 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C4-1 Extract the common base payload and have the review payload extend it, keeping serialized JSON byte-identical and ## Scope

- `src/aeat/application/ledger/_models.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C4-1 Extract the common base payload and have the review payload extend it, keeping serialized JSON byte-identical

## Scope

- `src/aeat/application/ledger/_models.py`

## Description

- Confirmed the conformance gate checks field-set + validation, not key order,
  and consumers read by key — so subclassing (which appends `review_status`) is
  shape-safe despite `review_status` having been mid-list in the duplicate.
- Made `LedgerTransactionReviewPayload` subclass `LedgerTransactionPayload`,
  adding only `review_status`; it now inherits the ~25 fields, the
  `source_jurisdiction` validator, and the strict-frozen config.
- Delegated the `ledger_transaction_review_payload` builder to
  `ledger_transaction_payload` via `model_dump()` (`TransactionId` is an
  `Annotated` str, so the strict re-validation round-trips).

## Outcome

Committed as `344c1311a`, tagged `relocation:LedgerTransactionReviewPayload`
(2 files, +8/-69). Ruff clean; full `test_json_schema_conformance.py` plus the
whole `application/ledger` suite (298 tests) green, including the
report-to-payload mirror harness and the interface-contract payload tests.

## Notes

The CLI-layer OutputSchema mirror in `_ledger_payloads.py` is left intact: it is
the deliberate app/CLI boundary mirror the conformance harness exists to police,
not duplication to collapse.
