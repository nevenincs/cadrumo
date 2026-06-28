---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
---



# `cli-workflow-redesign` Code Review


S1827-001 | MEDIUM | S1827 CLI handlers still own ledger result projection

`ledger_edit`, `ledger_classify`, and `ledger_allocate` delegate persistence to `update_manual_transaction_fields`, but the command module still converts the backend `Transaction` domain object into the public JSON/text shape through `_ledger_transaction_payload` and `_emit_update_result`. The governing ADR says CLI handlers must not implement schema conversion logic and must render backend/application results through standard emitters or schema emitters. This keeps the S1827 surface coupled to domain internals such as raw transaction dates, tax fields, lifecycle state, and review status; adding or changing backend fields now requires CLI-local projection changes instead of a backend-owned result schema.

Remediation: move the manual-ledger transaction response projection into an application result model or schema emitter, then have the CLI pass the typed backend result to `_emit` without unpacking transaction internals.

S1827-002 | MEDIUM | Reclassifying a row to personal preserves stale tax facts

`_command_from_patch` clears `business_pct` and `usage_ratio_id` when a patch changes classification away from `MIXED`, but it keeps existing `category_id`, `taxable_base`, `iva_rate`, `iva_amount`, `irpf_category`, and `prorrata_reference`. A behavior probe confirmed that classifying a previously business row as `PERSONAL` leaves the prior category and IVA facts persisted while emitting `ledger.transaction.classified`. The preflight path treats personal rows as ready and returns early, so this stale state is not reported even though the ledger transaction still carries aggregation-visible tax fields. That violates the backend validation expectation for class/category consistency and can leave audit-visible facts that no longer match the active classification.

Remediation: enforce classification-to-tax-field consistency in the backend command/patch path. Either clear incompatible tax/proportionality fields on non-business classifications or reject such patches unless the caller explicitly supplies a coherent replacement state. Add service and CLI tests that reclassify `BUSINESS`/`MIXED` rows to `PERSONAL` and verify the persisted tax fields and emitted events.

S1827-003 | LOW | Alias-removal coverage is too narrow for the S1827 command set

The scoped CLI test covers `set-ratio` as a rejected legacy alias, but S1827 exposes edit, classify, allocate, and proportionality behavior under the no-shim/no-alias rule. The test slice does not prove that other rejected spellings from the ledger ADR, such as `split`, or retired transaction-management roots remain absent from the active command tree for this specific lifecycle surface. The implementation search did not find those aliases in the reviewed command module, so this is a coverage gap rather than a confirmed exposed command.

Remediation: add negative command-discovery tests for the rejected S1827 spellings and legacy roots alongside the positive edit/classify/allocate flow. Keep the assertions behavior-based through the real Typer app, not by inspecting implementation strings.

## Verification

Reviewed the required plan and ADR grounding documents, the code-review template, the scoped ledger application and CLI files, operator help, and locale entries. Ran the scoped test slice with the existing virtualenv because `uv run` could not update a locked console script; `python -m pytest` reported `48 passed` for the scoped application and CLI tests.

## Remediation

S1827-001 remediation moved the ledger transaction JSON projection into the application ledger boundary through `ledger_transaction_payload`, `ledger_transaction_review_payload`, `ledger_transaction_result_payload`, and `ledger_transaction_tracking_payload`. The CLI now delegates mutation/read result schema construction to those backend-owned functions and only renders text lines through `_emit`.

S1827-002 remediation enforces backend consistency when a typed patch changes `business_classification` to a non-business state. The patch-to-command path clears incompatible category, tax, IRPF, usage-ratio, and prorrata facts before rebuilding the validated `ManualLedgerTransactionCommand`. A service test covers reclassifying a business row to `PERSONAL` and verifies the stale tax facts are removed.

S1827-003 remediation broadens real Typer command-surface coverage so rejected legacy spellings include both `set-ratio` and `split`.

Final verification after remediation:
- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/operator_surface/_help.py`
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/operator_surface/_help.py`
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_service.py -q` (`83 passed`)
- `uv run --no-sync python -m aeat.locales audit`

## Re-review 2026-05-14

No residual S1827 findings found in the focused re-review. Ledger transaction projection is now owned by the application ledger boundary through the exported projection helpers, with CLI code limited to command parsing and text-line rendering. Non-business reclassification clears stale category, tax, IRPF, usage-ratio, and prorrata facts through the typed patch service path. Legacy `set-ratio` and `split` spellings are covered through real Typer command behavior, and the reviewed remediation tests assert persisted service/CLI outcomes rather than tautological calculations.

Verification:
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py -q` (`49 passed`)
