---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e2b9809892e4365544ce952f776a3997e9f8ebf4f922e710376ef9d9990f2503'
step_id: 'S94'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Update typed-error consumer tests after the ledger reader cutover without asserting translated prose.

## Scope

- `src/cadrumo/llm/tests/test_llm_vision_classifier.py`

## Description

- Replace two stale `LLMClassifierError` and raw remediation-prose assertions with the imported `PurchaseInvoiceEvidenceInputError` contract.
- Assert the canonical `ProvisioningPreconditionCondition.RUNTIME_REACHABLE` identifier and structured `runtime_reachable` evidence fact.
- Preserve the distinction between reader unavailability and genuine available-reader operation failure without mirroring producer decision logic.

## Outcome

- Completed the immediate S38 consumer-test cutover in the assigned LLM vision classifier test module.
- All 5 focused classifier tests, 5 producer evidence tests, and 21 ledger CLI integration tests pass.
- Ruff check, Ruff format check, basedpyright, and diff whitespace validation pass for the assigned test module.
- S94 remains open because its remaining campaign test migration scope is intentionally deferred.

## Notes

- Tests use real loopback or unreachable network behavior already provided by the suite; no fake, mock, stub, patch, monkeypatch, skip, or xfail was introduced.
- No production or S38-owned files were edited.
