---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:700ba3254305111236bb7250173c38f6439ea8c3fc979453aeab108077bc8d8f'
step_id: 'S90'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate ledger CLI action producers and co-located renderers without independently authored command prose, including direct PurchaseInvoiceEvidenceInputError consumer migration in _ledger_llm_cli.py and _ledger_lifecycle_cli.py so S38 reader-unavailability verdicts reach the shared envelope intact.

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`
- `src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py`
- `src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_batch_cli.py`

## Description

- Remove local `LLMClassifierError` catches that redeclared producer failures as CLI-authored prose.
- Remove local `PurchaseInvoiceEvidenceInputError` string projections from split, lifecycle, extract, and confirm consumers.
- Propagate typed ledger failures to the shared command boundary so canonical precondition verdicts and action envelopes remain intact.
- Replace the obsolete test-only runtime condition identity with `ProvisioningPreconditionCondition.RUNTIME_REACHABLE` and values derived from it.
- Preserve operational failures as their registered typed errors without classifying them as false precondition failures.

## Outcome

- No `PurchaseInvoiceEvidenceInputError` catch or obsolete `provisioning.ollama.runtime_reachable` identity remains in the S90 CLI scope.
- Reader unavailability reaches the shared boundary as `PurchaseInvoiceEvidenceInputError` with its canonical terminal verdict; an available-reader operation failure remains `LLMClassifierError`.
- Ten isolated batch CLI tests, fourteen shared action-resolution tests, five producer distinction tests, and two real evidence refusal CLI paths pass.
- Ruff, format, compilation, focused BasedPyright, and diff checks pass for the changed surfaces.
- S90 remains open for coordinated re-review.

## Notes

- The wider evidence CLI run produced thirty-three passes and five environment-sensitive failures: four happy-path extraction cases require an unavailable local Ollama semantic reader, while the lone combined-run batch failure passes in isolation.
- Focused BasedPyright is clean for the changed application and test modules; the ledger evidence CLI module retains its pre-existing private shared-helper diagnostics.
- No compatibility bridge, locally authored action prose, plan mutation, ledger mutation, or step closure was added.
