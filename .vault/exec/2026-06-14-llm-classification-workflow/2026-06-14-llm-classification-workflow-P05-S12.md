---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S12'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Add ledger list --hide-llm-rejected: an event-based filter excluding rows whose latest LLM decision is a rejection, keeping review_status a pure projection

## Scope

- `src/aeat/entrypoints/cli/_ledger_list.py`
- `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `src/aeat/locales`
- `tests`

## Description

- Add `latest_llm_decision_is_rejection` + an `exclude_llm_rejected` path to `project_ledger_list`: load the event catalogue once and drop rows whose latest LLM-decision event (classified vs rejected) is a rejection.
- Add the `ledger list --hide-llm-rejected` flag threading the exclusion; add the locale key (en/es/ca/hu).
- Verify the 7b deferral: pulled `qwen2.5vl:7b` (network recovered) and ran a live end-to-end vision classification; updated the prior audit BLOCKED->RESOLVED.

## Outcome

The batch reviewer can hide reviewed-and-declined rows from `ledger list`; review_status stays a pure projection (event-based orthogonal filter). 1 CLI test; conformance/size green. qwen2.5vl:7b live-verified.

## Notes

The exclusion reads events per listed row from one loaded catalogue; it never consults review_status. Closes the last two deferrals (declined filter + 7b weights).

