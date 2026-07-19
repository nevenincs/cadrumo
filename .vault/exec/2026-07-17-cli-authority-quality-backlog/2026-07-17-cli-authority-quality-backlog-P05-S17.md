---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S17'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Prove suggestion, saturation, rejection, no-split, multi-child split, invocation-origin attribution, and CLI-route parity against real persistence and model subprocess boundaries

## Scope

- `src/cadrumo/application/ledger/tests/test_llm_reject.py`

## Description

- Extend the review-workflow real-behaviour suite and the reject suite (real SQLite persistence in isolated profiles, real model-subprocess proposer/classifier boundaries via the injected `SubprocessLLMClassifier` seams, no mocks/stubs/skip/xfail) to cover the full decision matrix routed through `execute_reviewed_decision`.
- Prove saturation apply: the registry-derived IVA substrate (base 100.00, rate 0.21, amount 12.60/21.00) persists and the `LEDGER_TRANSACTION_CLASSIFIED` event carries the CLASSIFY_LLM_SATURATE_APPLY-derived `source_command`.
- Prove multi-child evidence split apply: two classified children persist and each is stamped with the CLASSIFY_AUTO_SPLIT origin label; the parent transitions to SPLIT.
- Prove the split --llm route stamps its own distinct SPLIT_LLM label, and that the two split origins yield distinct labels.
- Prove the no-split (single-child) verdict refuses a SPLIT decision and persists nothing (parent stays ACTIVE).
- Prove invocation-origin attribution is derived, total, non-blank, and unique across all six origins (asserted against `origin.source_command`, never a hardcoded copy).
- Prove CLI-route parity: routing classify --llm --apply and the auto-split apply through the workflow persists an IDENTICAL transaction / identical child business projection and audit label to the pre-cutover direct-primitive call carrying the same source_command, run in two independent isolated profiles.
- Prove reject-route parity: the workflow reject (CLASSIFY_LLM_REJECT) persists the same durable `source_command` the pre-cutover direct `reject_llm_suggestion` default produced.

## Outcome

- 16 tests in `test_llm_review_workflow.py` and the extended `test_llm_reject.py` pass; the full application-layer ledger LLM suite is 64 passed. ruff, ty, and pyright (via `just check-types`) all green. Committed as `b968f90bee`.
- Modified files: `src/cadrumo/application/ledger/tests/test_llm_review_workflow.py`, `src/cadrumo/application/ledger/tests/test_llm_reject.py`.

## Notes

- The CLI-route parity comparison excludes only non-deterministic wall-clock stamps (`classified_at` / `created_at` / `modified_at`) and, for split children, the regenerated ingest-provenance hash and per-write event ids (`source_sha256`, `created_event_id`, `edit_lineage` event ids). Every business-meaningful field — classification, expense/IVA substrate, amounts, provenance labels, `source_command`, split lineage, split_group_id — is compared and MUST be identical between the direct-primitive and workflow-routed paths. The projection is documented in `_child_business_projection`.
- The real model-subprocess boundary is the injected `SubprocessLLMClassifier` (a real Python subprocess emitting the proposal/classification JSON), reused from `_llm_evidence_split_support` and `_llm_saturation_support`; this exercises the real parse/derive path without requiring a vendor LLM CLI on PATH.
- The plan pins S17's file to `test_llm_reject.py`; the split/saturation/parity matrix was authored in `test_llm_review_workflow.py` (the S15 pattern the resumer brief named as the one to extend), with the reject-route parity added to `test_llm_reject.py`.
