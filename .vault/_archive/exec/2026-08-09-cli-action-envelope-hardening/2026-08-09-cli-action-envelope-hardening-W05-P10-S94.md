---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:4343edb8305792fbd0e2fade7ac3ab3544bc88d75666549f8cfd33be967abb13'
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

- Add the closed LLM-owned `LLMPreconditionCondition` vocabulary and deferred application-verdict constructor with stable scalar facts, declared provenance, and explicit no-recovery outcomes.
- Preserve provisioning verdicts and nested typed `LLMValidationError` instances instead of rebuilding message or command hints.
- Keep producer tests on public LLM and application contracts; CLI projection extraction belongs exclusively to S114.

## Outcome

- LLM-originated refusals carry application-owned condition evidence and explicit outcomes rather than producer prose.
- `test_evidence_draft_text.py` no longer imports or calls private `entrypoints.cli._common.cli_policy_refusal_projection`.
- The evidence-text test proves the producer-level `PurchaseInvoiceEvidenceInputError` verdict directly and proves Pydantic preserves a nested public `LLMValidationError` with its exact typed verdict.
- No compatibility facade or duplicate CLI projection logic was added.
- S94 remains open for independent review.

## Validation

- `uv run pytest -q src/cadrumo/llm/tests/test_evidence_draft_text.py` - 45 passed.
- `uv run pytest -q src/cadrumo/llm/tests` - 460 passed; three serial tests were honestly withheld by the xdist marker hook.
- `uv run ruff check src/cadrumo/llm` - passed.
- `uv run ty check src/cadrumo/llm` - passed.
- Import-hygiene gate - 16 passed and three failures, all caused by concurrent private imports in `entrypoints/cli/tests/test_ledger_filer_precondition_projection.py`; S94's former private CLI import is absent.

## Cross-owner handoffs

- S114 must test extraction of the nested `ValidationError.errors()[...]["ctx"]["error"]` `LLMValidationError`, then resolve its attached verdict through the shared CLI projection boundary. S94 deliberately does not reach into CLI projection code to make that assertion.
- S90/CLI still owns preservation of typed LLM consent refusals in ledger evidence commands.

## Independent review

Keep S94 open. Independently verify the producer-level nested-error proof and the exact S114 handoff before closure.

## Notes

- The LLM-test scan found older private application reaches, test doubles, and message assertions outside this narrow closure blocker; none were introduced or expanded here, and changing their architecture would exceed this S94 closure slice.

## Coordinated canonical rehoming reconciliation

A fresh read-only derivation established three identical stability boundaries separated by at least sixty seconds. Immediately before mutation, the canonical guard revalidated the ledger, plan, all-source, rendered postimage, structural-delta, and locator-delta hashes byte-for-byte. OWNER_ZERO was zero and every one of the twenty-four structural additions had exactly one open owner. The delta contained thirty-five removals, no historical-row, disposition, or current-identity changes, and 144 locator-only refreshes recorded as incidental metadata.

Exactly one S50 canonical-tool write produced the proven postimage. The resulting ledger SHA-256 is `bc6ddc3b5edddd852a155e48ca58ec6e3aa188f716cecef8615b9bef20de2aec`. Direct validation returned `E_REHOMING_VALIDATED:238`; the single immediate no-write replay returned `E_REHOMING_MIGRATION_CHECKED:238`. No second locator chase or write was performed. The complete canonical rehoming lane passed 74 tests.

This owner Step remains open for independent review and ledger reconciliation.
