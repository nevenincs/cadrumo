---
tags:
  - '#plan'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-15'
tier: L2
related:
  - '[[2026-06-14-llm-classification-workflow-adr]]'
  - '[[2026-06-14-llm-classification-workflow-research]]'
---


# `llm-classification-workflow` plan

### Phase `P01` - Domain: no-split verdict + multiplicity signal

Relax LLMSplitResponse to a single-child no-split verdict and add multiple_components to LLMClassificationResponse; update prompts.

- [x] `P01.S01` - Relax LLMSplitResponse to >=1 child + recommends_split; `relax derive_child_amounts; update build_split_prompt for the single-line verdict; `src/aeat/domain/transactions/_llm.py, src/aeat/application/ledger/_evidence_split.py`.
- [x] `P01.S02` - Add multiple_components to LLMClassificationResponse; `ask for it in the classification prompt when evidence is present; `src/aeat/domain/transactions/_llm.py`.

### Phase `P02` - Application + CLI: recommendation Notice and auto-split route

Carry multiple_components into suggestions, emit the typed split-recommendation Notice, add classify --auto-split routing into the evidence split and in-place classification.

- [x] `P02.S03` - Carry multiple_components into LLMClassificationSuggestion + LLMSaturatedSuggestion; `add recommends_split; add apply_evidence_classification; guard apply_evidence_split; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `P02.S04` - Emit typed split-recommendation Notice from classify; `add --auto-split routing into the evidence split / in-place classify; `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `P03` - Tests, locales, docs

Real-behaviour tests for the no-split verdict, recommendation Notice, and auto-split route; locale keys via the CLI; how-to update.

- [x] `P03.S05` - Real-behaviour tests: no-split verdict, in-place apply, auto-split route, recommendation Notice; `src/aeat/application/ledger/tests, src/aeat/entrypoints/cli/tests`.
- [x] `P03.S06` - Add locale keys via aeat.locales; `update classify-with-llm how-to with the auto-split flow; `src/aeat/locales, docs/how-to/classify-with-llm.md`.

### Phase `P04` - Audit-trailed reject: the fourth decision terminal (F10)

Add the LLM-suggestion-rejected event, reject_llm_suggestion, classify --reject CLI, history/view surfacing, locales, docs, and tests, closing the review loop.

- [x] `P04.S07` - Add BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED + catalogue pin test; `src/aeat/domain/buckets/_event.py, src/aeat/domain/buckets/tests/test_event_catalogue.py`.
- [x] `P04.S08` - Add reject_llm_suggestion + LLMSuggestionRejectionResult emitting the rejection event without mutating the transaction; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `P04.S09` - Add classify --reject (stage-1/saturate/auto-split) and surface the rejection in ledger history; `src/aeat/entrypoints/cli/_ledger.py, src/aeat/entrypoints/cli/_ledger_llm_cli.py, src/aeat/entrypoints/cli/_ledger_read_cli.py`.
- [x] `P04.S10` - Real-behaviour tests for reject (event recorded, no mutation, history/view); `locales; how-to review-loop section; `src/aeat/application/ledger/tests, src/aeat/entrypoints/cli/tests, src/aeat/locales, docs/how-to/classify-with-llm.md`.

### Phase `P05` - Surfacing follow-ups: ledger view rejection notice

Surface the most-recent LLM rejection on ledger view as a typed info notice, the deferred view one-liner from the review-loop ADR.

- [x] `P05.S11` - Surface the latest LLM rejection on ledger view as a typed info notice reading the row's LLM-decision events; `src/aeat/entrypoints/cli/_ledger_read_cli.py, src/aeat/locales, docs/how-to/classify-with-llm.md, tests`.
- [x] `P05.S12` - Add ledger list --hide-llm-rejected: an event-based filter excluding rows whose latest LLM decision is a rejection, keeping review_status a pure projection; `src/aeat/entrypoints/cli/_ledger_list.py, src/aeat/entrypoints/cli/_ledger_read_cli.py, src/aeat/locales, tests`.

## Description


## Steps







## Parallelization


## Verification
