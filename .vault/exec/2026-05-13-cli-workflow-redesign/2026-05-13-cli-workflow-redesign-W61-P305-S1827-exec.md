---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P305.S1827'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p305-s1827-code-review-audit]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-ledger-ratios-eligible-and-validate-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]"
---

# `cli-workflow-redesign` `W61.P305.S1827`

Closed plan rows:

- `W61.P305.S1827`

## Description

Exposed `aeat app ledger edit`, `aeat app ledger classify`, and `aeat app ledger allocate` through the redesigned thin CLI boundary for the active profile bucket.

The commands parse operator options, build a typed `ManualLedgerTransactionPatch`, delegate mutation to `update_manual_transaction_fields`, and render through `_emit`. They do not own persistence, schema conversion, event construction, or ledger business rules.

Application ledger now owns the shared result projection through `ledger_transaction_payload`, `ledger_transaction_result_payload`, `ledger_transaction_review_payload`, and `ledger_transaction_tracking_payload`. That keeps transaction JSON shape and review-status derivation out of the CLI module.

The backend patch path now enforces classification consistency. Reclassifying a bucket-scoped manual ledger transaction to a non-business state clears stale category, taxable-base, IVA, IRPF, usage-ratio, business/private proportionality, and prorrata facts before rebuilding the validated `ManualLedgerTransactionCommand`.

Event emission remains backend-owned. Updates emit `ledger.transaction.updated`, `ledger.transaction.classified`, and `ledger.transaction.allocated` according to the changed field families.

Rejected legacy spellings remain absent. Real Typer command-surface tests cover `set-ratio` and `split` as unregistered commands.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1827-code-review-audit.md`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/application/operator_surface/_help.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_cli_surface.py`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/hu.yml`

## Tests

- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/operator_surface/_help.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/operator_surface/_help.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_service.py -q`
  - 83 passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py -q`
  - 49 passed during re-review
- `uv run --no-sync python -m aeat.locales audit`
  - `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` passed

Coverage includes real CLI initialization, manual ledger create/edit/classify/allocate in the active profile bucket, backend patch validation, non-business reclassification cleanup, bucket-event emission, usage-ratio reference validation, and negative command discovery for rejected legacy spellings.

## Review

Formal code review found three S1827 issues: CLI-owned ledger projection, stale tax facts after personal reclassification, and narrow alias-removal coverage.

All three findings were resolved. Re-review reported no residual S1827 findings in `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1827-code-review-audit.md`.

## Outcome

`W61.P305.S1827` is complete. The ledger command surface now supports bucket-scoped `edit`, `classify`, and `allocate` flows under `aeat app ledger`, with typed application-service delegation, backend-owned projection, classification cleanup, event emission, locale parity, and passing focused validation.
