---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:ad30a8433e6c5cc1e45d5b07b07676c883629f9dee8f9da08e5bb8a72f911111'
step_id: 'S38'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Consume the S33 typed reader-availability facts at _batch_ingest.py and _llm_classification.py within the exclusive ledger area, retain no MissingOptionalExtraError prose or compatibility bridge, and preserve only explicit typed reader-availability verdicts

## Scope

- `src/cadrumo/application/ledger`

## Description

- Replace batch inference-pause reason, detail, remediation, and cause copies with S33 facts and a mandatory precondition verdict.
- Preserve the exact S33 reader-unavailability verdict when an on-host reader call fails and its confirmation probe is unavailable.
- Keep an operation failure whose confirmation probe is available distinct from a reader-unavailability precondition.
- Update real batch pacing and closed-port reader coverage without a compatibility field or authored command text.

## Outcome

Open for coordinated review and the S90 and S94 downstream consumer migrations.

## Notes

- S90 owns CLI catches and renderers for the typed PurchaseInvoiceEvidenceInputError handoff.
- S94 owns the LLM-layer consumer proof at `src/cadrumo/llm/tests/test_llm_vision_classifier.py`.
- The focused S38 application tests pass. The current LLM-layer test still asserts its retired LLMClassifierError and prose contract, intentionally without a compatibility bridge.
