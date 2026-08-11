---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:b57886b9ca074e9371db419249f6e85ac3b6bc498f20c77f80c030c90a3b4fac'
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
- Correct the classifier contract to name `PurchaseInvoiceEvidenceInputError` and its exact provisioning verdict without transport or localized wording.
- Update real batch pacing and closed-port reader coverage without a compatibility field or authored command text.

## Outcome

- The application producer preserves the exact provisioning verdict through `PurchaseInvoiceEvidenceInputError` when reader availability is not satisfied.
- A reader call that fails after the confirmation probe reports availability remains `LLMClassifierError`, so no false precondition is invented.
- The stale classifier contract now documents both typed outcomes accurately.
- Five focused reader-contract tests and the wider shared action projection tests pass.
- S38 remains open for coordinated re-review.

## Notes

- S90 owns CLI propagation of the typed `PurchaseInvoiceEvidenceInputError` handoff.
- S94 owns the LLM-layer consumer proof at `src/cadrumo/llm/tests/test_llm_vision_classifier.py`.
- No `MissingOptionalExtraError` prose, compatibility field, duplicate exception identity, or locale-specific action wording was introduced.
