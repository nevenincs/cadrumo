---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S09'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Add classify --reject (stage-1/saturate/auto-split) and surface the rejection in ledger history

## Scope

- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/_ledger_llm_cli.py`
- `src/aeat/entrypoints/cli/_ledger_read_cli.py`

## Description

- Add `classify --reject --reason` across the stage-1, saturate, and auto-split routes (mutually exclusive with --apply).
- Add `LedgerClassifyLlmRejectResult` payload + `emit_llm_rejection` shared helper + split-recommendation Notice.
- Add the rejection event to the `ledger history` displayed-event allowlist.
- Extract LLM CLI routing into `_ledger_llm_cli.py` and the LLM result payloads into `_ledger_llm_payloads.py` to keep `_ledger.py` and `_ledger_payloads.py` within the module-size budget.

## Outcome

`classify --reject` records a declined suggestion visible in `ledger history`; size gate, conformance, and parity all green.

## Notes

The classify helpers were renamed public (`ledger_classify_llm` etc.) on extraction; `_ledger_autosplit_cli.py` was renamed to `_ledger_llm_cli.py` for naming honesty.

