---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S07'
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
     The S07 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Add BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED + catalogue pin test and ## Scope

- `src/aeat/domain/buckets/_event.py`
- `src/aeat/domain/buckets/tests/test_event_catalogue.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED + catalogue pin test

## Scope

- `src/aeat/domain/buckets/_event.py`
- `src/aeat/domain/buckets/tests/test_event_catalogue.py`

## Description

- Add `BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED` (`ledger.transaction.llm_suggestion.rejected`).
- Pin the value in the event-catalogue test.

## Outcome

The rejection event type exists and is catalogue-pinned.

## Notes

None.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
