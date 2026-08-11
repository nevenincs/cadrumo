---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:2e64492be56abf2e6b033b2bbc2c8257e0f3bfd1f1963020558a5575b68abc2e'
step_id: 'S94'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Update LLM action-envelope consumers and typed failure boundaries without retaining prose recovery authority.

## Scope

- `src/cadrumo/llm`

## Description

- Replace the removed `ModelSelection.detail` read in column-role model resolution with the producer's machine facts and exact terminal precondition verdict.
- Extend `LLMConfigError` with the established typed terminal-verdict carrier used by the sibling contention error.
- Preserve the no-candidate `operator_decision` outcome without a fallback message or invented action.
- Remove both Anthropic optional-extra exception-string bridges and propagate `MissingOptionalExtraError` unchanged from the core dependency boundary.
- Replace stale vision classifier message assertions with typed reader-availability verdict assertions.
- Replace optional-extra install-prose assertions with registered extra identity facts and cover both the client adapter builder and provider SDK loader in a fresh interpreter.
- Run a fixed-point package scan for removed provisioning DTO fields, `install_hint` consumers, optional-extra rewrapping, raw install commands, and recovery-command fields.

## Outcome

- Column-role selection failure now carries `provisioning.selected_model.available`, its exact evidence, no action, and `operator_decision` through `LLMConfigError`.
- Both Anthropic dependency boundaries expose the same unchanged `MissingOptionalExtraError` machine identity and registered extra facts.
- The previously migrated contention and vision paths retain their exact typed provisioning verdicts.
- Twenty-three column-role tests, four optional-extra boundary tests, eleven contention tests, five vision tests, and eight client tests pass.
- Ruff check and formatting pass for all owned files; focused basedpyright reports zero diagnostics; Python compilation and diff whitespace validation pass.
- S94 remains open for independent re-review.

## Notes

- No fake, mock, stub, patch, monkeypatch, skip, xfail, message matching, compatibility bridge, core/application layering import, or hardcoded recovery command was introduced.
- The fixed-point production scan has zero removed provisioning fields, `install_hint` consumers, optional-extra rewrappers, raw install commands, or recovery-command fields. Remaining exception-string sites represent response validation, rasterisation, or provider-operation diagnostics rather than recovery authority.
- CLI action and schema gates are externally red because concurrent Modelo code declares no `OperatorActionAxis` for `ModeloVerificationFindingKind.ADVISORY`; collection and six action-resolution cases stop at that import-time invariant.
- The historical-default rehoming validator is externally red on fingerprint drift for `PurchaseInvoiceEvidenceInputError`, `PurchaseInvoiceEvidenceNotFoundError`, and `LLMContentionError`; this S94 remediation does not edit the ledger producers, contention constructor, or rehoming evidence.
