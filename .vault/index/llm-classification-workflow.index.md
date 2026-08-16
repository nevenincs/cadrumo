---
generated: true
tags:
  - '#index'
  - '#llm-classification-workflow'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:9a40f7383c28923b49136d6a0562447bcbe498132341c4a35282a7de73adc06e'
related:
  - '[[2026-06-14-llm-classification-workflow-P01-S01]]'
  - '[[2026-06-14-llm-classification-workflow-P01-S02]]'
  - '[[2026-06-14-llm-classification-workflow-P02-S03]]'
  - '[[2026-06-14-llm-classification-workflow-P02-S04]]'
  - '[[2026-06-14-llm-classification-workflow-P03-S05]]'
  - '[[2026-06-14-llm-classification-workflow-P03-S06]]'
  - '[[2026-06-14-llm-classification-workflow-P04-S07]]'
  - '[[2026-06-14-llm-classification-workflow-P04-S08]]'
  - '[[2026-06-14-llm-classification-workflow-P04-S09]]'
  - '[[2026-06-14-llm-classification-workflow-P04-S10]]'
  - '[[2026-06-14-llm-classification-workflow-P05-S11]]'
  - '[[2026-06-14-llm-classification-workflow-P05-S12]]'
  - '[[2026-06-14-llm-classification-workflow-adr]]'
  - '[[2026-06-14-llm-classification-workflow-audit]]'
  - '[[2026-06-14-llm-classification-workflow-plan]]'
  - '[[2026-06-14-llm-classification-workflow-research]]'
  - '[[2026-06-15-llm-classification-workflow-adr]]'
  - '[[2026-06-15-llm-classification-workflow-audit]]'
---

# `llm-classification-workflow` feature index

Auto-generated index of all documents tagged with `#llm-classification-workflow`.

## Documents

### adr

- `2026-06-14-llm-classification-workflow-adr` - `llm-classification-workflow` adr: `LLM classification workflow contract: split recommendation, evidence-driven auto-split, and the review loop` | (**status:** `accepted`)
- `2026-06-15-llm-classification-workflow-adr` - `llm-classification-workflow` adr: `Audit-trailed LLM review loop: explicit reject as the fourth decision terminal` | (**status:** `accepted`)

### audit

- `2026-06-14-llm-classification-workflow-audit` - `llm-classification-workflow` audit: `Campaign-close honesty review: split recommendation and auto-split`
- `2026-06-15-llm-classification-workflow-audit` - `llm-classification-workflow` audit: `Campaign-close honesty review: audit-trailed reject terminal (F10)`

### exec

- `2026-06-14-llm-classification-workflow-P01-S01` - Relax LLMSplitResponse to >=1 child + recommends_split
- `2026-06-14-llm-classification-workflow-P01-S02` - Add multiple_components to LLMClassificationResponse
- `2026-06-14-llm-classification-workflow-P02-S03` - Carry multiple_components into LLMClassificationSuggestion + LLMSaturatedSuggestion
- `2026-06-14-llm-classification-workflow-P02-S04` - Emit typed split-recommendation Notice from classify
- `2026-06-14-llm-classification-workflow-P03-S05` - Real-behaviour tests: no-split verdict, in-place apply, auto-split route, recommendation Notice
- `2026-06-14-llm-classification-workflow-P03-S06` - Add locale keys via aeat.locales
- `2026-06-14-llm-classification-workflow-P04-S07` - Add BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED + catalogue pin test
- `2026-06-14-llm-classification-workflow-P04-S08` - Add reject_llm_suggestion + LLMSuggestionRejectionResult emitting the rejection event without mutating the transaction
- `2026-06-14-llm-classification-workflow-P04-S09` - Add classify --reject (stage-1/saturate/auto-split) and surface the rejection in ledger history
- `2026-06-14-llm-classification-workflow-P04-S10` - Real-behaviour tests for reject (event recorded, no mutation, history/view)
- `2026-06-14-llm-classification-workflow-P05-S11` - Surface the latest LLM rejection on ledger view as a typed info notice reading the row's LLM-decision events
- `2026-06-14-llm-classification-workflow-P05-S12` - Add ledger list --hide-llm-rejected: an event-based filter excluding rows whose latest LLM decision is a rejection, keeping review_status a pure projection

### plan

- `2026-06-14-llm-classification-workflow-plan` - `llm-classification-workflow` plan

### research

- `2026-06-14-llm-classification-workflow-research` - `llm-classification-workflow` research: `LLM classification workflow: review/approve/reject loop and evidence-driven auto-split`
