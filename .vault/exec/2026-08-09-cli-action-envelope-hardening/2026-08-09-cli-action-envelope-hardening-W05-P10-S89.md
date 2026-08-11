---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:02eff00c6addda18dd108dff6c4dc9f5905fbda28c9852e6941a11526fbd1e45'
step_id: 'S89'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Complete the consumer half of the atomic S33/S89 provisioning cutover by replacing config-check and provision payload and renderer free-form detail and remediation forwarding plus raw Google package prose with the exact S33 typed projection and resolved action or no-recovery rendering, never hardcoding command or English text

## Scope

- `src/cadrumo/entrypoints/cli/_config`
- `src/cadrumo/entrypoints/cli/tests/test_provision_model_selection_action_recovery.py`

## Description

- Project provisioning dependency, selection, contention, pull, and readiness facts through the shared CLI precondition resolver.
- Preserve the complete `ModelSelection` result through pull and verify target resolution instead of discarding its failed precondition verdict.
- Emit failed selection as the registered pull or verify result with the exact S33 facts and resolved no-recovery projection.
- Remove the failed-selection path through localized `BadParameter` prose while retaining fail-closed validation for an impossible verdict-free failure.
- Prove the production selection builder with a context requirement of `1_000_000` tokens across every supported locale in JSON and text.

## Outcome

- Pull and verify now emit `provisioning.selected_model.available`, the producer evidence values, no action, and `operator_decision` when no catalogued candidate satisfies the configured context.
- The result schemas admit a null model only for the typed pre-selection refusal while retaining strict nonempty model validation when present.
- Four S89 integration cases, two existing provisioning integration cases, fourteen schema and action-resolution cases, and twenty-eight application selection cases pass.
- Ruff check and format, focused basedpyright, Python compilation, and diff whitespace validation pass.
- S89 remains open for independent re-review.

## Notes

- Tests invoke the production selector and pull or verify handlers; no fake, mock, stub, patch, monkeypatch, skip, xfail, message matching, or copied selection predicate was introduced.
- The full historical-default rehoming validator is currently red on unrelated concurrent fingerprint drift for `PurchaseInvoiceEvidenceInputError`, `PurchaseInvoiceEvidenceNotFoundError`, and `LLMContentionError`; this S89 slice changes none of those producers or registry evidence.
- S33, S38, S90, and S94 files were not edited.
