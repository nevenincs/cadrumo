---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S08'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace llm-classification-workflow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Add reject_llm_suggestion + LLMSuggestionRejectionResult emitting the rejection event without mutating the transaction and ## Scope

- `src/aeat/application/ledger/_llm_classification.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add reject_llm_suggestion + LLMSuggestionRejectionResult emitting the rejection event without mutating the transaction

## Scope

- `src/aeat/application/ledger/_llm_classification.py`

## Description

- Add `reject_llm_suggestion` + `LLMSuggestionRejectionResult`: emits the rejection event capturing the proposal (classification/category/iva or split child_count) + operator reason, persisted through the transaction repository's secure-write batch (unchanged catalogue), mutating nothing.
- Re-export both from the package top level.

## Outcome

A rejection records a captured audit event and leaves the row unclassified; verified by 5 real-behaviour tests.

## Notes

Persisted via `_save_transaction_catalogue_and_events` (not a bare event-repo save) so the default CLI event repo binds to the active bucket, mirroring the apply path.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
