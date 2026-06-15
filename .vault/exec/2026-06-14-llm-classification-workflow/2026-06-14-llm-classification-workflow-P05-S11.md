---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S11'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Surface the latest LLM rejection on ledger view as a typed info notice reading the row's LLM-decision events

## Scope

- `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `src/aeat/locales`
- `docs/how-to/classify-with-llm.md`
- `tests`

## Description

- Add `_latest_llm_rejection_notice`: read the row's LLM-decision events (CLASSIFIED + LLM_SUGGESTION_REJECTED), and when the most recent is a rejection, return a typed `info` Notice carrying the operator reason.
- Wire it into `ledger view`: surface the notice + a text line via `_emit_envelope(notices=...)`.
- Add `cli.ledger.view.llm_rejected_notice` / `llm_rejected_label` locales (en/es/ca/hu); document on the classify-with-llm how-to.

## Outcome

`ledger view` flags when the most recent LLM suggestion was rejected, with the reason — the deferred view one-liner from the review-loop ADR. 2 CLI tests; conformance/parity/size all green.

## Notes

The notice rides the Notice channel (cli-notices-are-the-only-diagnostic-channel); `ledger view`'s result schema is unchanged. review_status stays a pure projection (the rejection is surfaced, not folded into status).

