---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:b2222b113d23e104b9e92f816ee3fbd782e752a915568bc3d31ec88b785e7a47'
step_id: 'S94'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Update LLM action-envelope producers and failure boundaries with typed, locale-neutral outcomes.

## Scope

- `src/cadrumo/llm/_preconditions.py`
- `src/cadrumo/llm/_errors.py`
- `src/cadrumo/llm/_client.py`
- `src/cadrumo/llm/_consent.py`
- `src/cadrumo/llm/_column_role_mapping.py`
- `src/cadrumo/llm/_evidence_draft_text.py`
- `src/cadrumo/llm/_evidence_draft_vision.py`
- `src/cadrumo/llm/_invoice_field_grounding.py`
- `src/cadrumo/llm/_models.py`
- `src/cadrumo/llm/_providers/{anthropic,base,gemini,local,openai}.py`
- LLM package tests for local admission, consent, column mapping, evidence readers, provider transport, model validation, and vision capability.

## Description

- Add the closed LLM-owned `LLMPreconditionCondition` vocabulary and one deferred application-verdict constructor. Each producer supplies stable scalar observation facts, declared provenance, and an explicit `operator_decision` no-recovery outcome; no command, help, hint, or display prose is embedded.
- Carry the verdict on existing LLM configuration, contention, busy, consent, and validation exceptions. Preserve provisioning's existing contention verdict instead of redeclaring it.
- Replace dynamic exception-message bridges and user-facing provider labels at LLM boundaries with canonical provider identities, typed error kinds, status values, model identities, and response-state facts. Genuine provider and PDF-rasterisation failures remain registered error families with machine facts, not invented recovery actions.
- Bind real LLM refusal predicates: local inference admission, evidence consent and token ephemerality, off-host model naming, provider credential presence and selection, vision support, column mapping response shape, evidence content/image/transcription presence, invoice response shape, and LLM model validation. The core `MissingOptionalExtraError` remains propagated unchanged rather than rewrapped.
- Make the tests assert the exact condition id, evidence, action absence, and no-recovery outcome over production local loopback transport and installed core-only product cohorts. The evidence-reader refusal also crosses the shared CLI projection resolver.

## Outcome

- LLM-originated terminal refusals carry application-owned, schema-resolvable condition evidence rather than producer prose or ad-hoc next-step hints.
- Provider and local-reader diagnostics retain locale-neutral machine facts; presentation remains renderer-owned through the registered error and localisation path.
- The S94 implementation is committed in the shared branch and remains open for independent re-review.

## Validation

- `uv run --no-sync pytest src/cadrumo/llm/tests` - 459 passed in 50.17s; the runner correctly reported three serial tests withheld from xdist.
- `uv run --no-sync pytest -n 0 -m "integration and serial and not perf and not os_keychain" src/cadrumo/llm/tests/test_anthropic_optional_extra_boundary.py::test_client_and_provider_loader_preserve_the_registered_extra_facts` - 1 passed in 200.96s.
- `uv run --no-sync pytest -n 0 -m "integration and serial and not perf and not os_keychain" src/cadrumo/llm/tests/test_missing_llm_extra_refuses_instructively.py::test_every_guarded_surface_preserves_the_registered_extra_facts` - 1 passed in 205.27s.
- `uv run --no-sync pytest -n 0 -m "integration and serial and not perf and not os_keychain" src/cadrumo/llm/tests/test_missing_llm_extra_refuses_instructively.py::test_the_driven_inventory_covers_every_guarded_entry_point` - 1 passed in 0.49s.
- `uv run --no-sync ruff check src/cadrumo/llm` - passed.
- `uv run --no-sync ty check src/cadrumo/llm` - passed.

## Cross-owner handoffs

- S114 owns generic CLI exception projection. Pydantic preserves LLM model-validator errors as `ValidationError.errors()[...]["ctx"]["error"]`; the shared CLI projection currently only reads an exception-level `terminal_precondition_verdict`. The S114 boundary must extract that nested typed error or explicitly classify that construction boundary.
- S90/CLI owns `src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`. Its `LLMConsentError` catch raises `_bad(str(exc))`, bypassing the typed terminal verdict and shared CLI projection. It must preserve or project the existing verdict instead.

## Independent review

Keep S94 open. Re-run the LLM tests and independently verify the two cross-owner consumers before closure.

## Notes

- `basedpyright src/cadrumo/llm` reports 24 pre-existing strict diagnostics in `_client.py`, provider adapter protocol visibility and Anthropic SDK unknown types, and `conftest.py`; all documented patterns occur in the parent of the S94 implementation commit.
- The feature-filtered body-section check reports three pre-existing missing sections in the separate S56 audit record. S94 itself is schema-complete.
