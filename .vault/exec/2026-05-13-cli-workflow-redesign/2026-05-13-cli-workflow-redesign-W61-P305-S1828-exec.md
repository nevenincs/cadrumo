---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P305.S1828'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p305-s1828-code-review-audit]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]"
---

# `cli-workflow-redesign` `W61.P305.S1828`

Closed plan rows:

- `W61.P305.S1828`

## Description

Exposed `aeat app ledger attach`, `archive`, `stash`, `remove`, `reset`, and `export` under the active profile bucket.

The command handlers remain thin. `attach` delegates to `attach_manual_transaction_evidence`; `archive` delegates to `archive_manual_transaction`; `stash` delegates to `stash_manual_transaction`; `remove` delegates to `remove_manual_transaction`; `reset` delegates to `reset_ledger_catalogue`; and `export` delegates to `export_ledger_transactions` with a typed `LedgerExportCommand`.

`attach` links existing secure evidence objects to a `ledger_transaction`. It supports the canonical `purchase_invoice_evidence` reference and supplementary `attachment_ids`; evidence existence, bucket ownership, and linked-object validation remain in the backend.

`archive` and `stash` are lifecycle transitions recorded on the ledger transaction with bucket events and lifecycle lineage. They do not move evidence or create compatibility state.

`remove` and `reset` require explicit `--yes` confirmation unless `--dry-run` is passed. This keeps destructive ledger changes deliberate while preserving backend finalized-modelo blockers and dry-run reporting.

`export` writes a prepared internal ledger artifact from canonical bucket-scoped rows. The application export service writes the output file before recording the durable `ledger.transaction.exported` bucket event, so event history does not claim a delivered artifact when the file write fails.

Backend-owned operator help and locale catalogues now include the S1828 command vocabulary.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1828-code-review-audit.md`
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

- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/application/export src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/operator_surface/_help.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/application/export src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/operator_surface/_help.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/application/ledger/test_models.py src/aeat/application/export/test_tabular.py -q`
  - 50 passed
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_surface.py -q`
  - 13 passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_service.py -q`
  - 86 passed
- `uv run --no-sync python -m aeat.locales audit`
  - `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` passed

Coverage includes real active-bucket CLI flows for attach, archive, stash, remove dry-run, confirmed remove, export, reset dry-run, confirmed reset, backend attach delegation, export write-before-event ordering, and locale parity.

## Review

Formal code review found three S1828 issues: missing confirmation gates on destructive `remove` and `reset`, export event persistence before output-file delivery, and incomplete curated operator help.

All three findings were resolved. Re-review reported no residual S1828 implementation findings in `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1828-code-review-audit.md`.

## Outcome

`W61.P305.S1828` is complete. The ledger command surface now supports bucket-scoped evidence attachment, lifecycle archive/stash, guarded remove/reset, and prepared ledger export under `aeat app ledger`, with backend delegation, event-history safety, locale parity, and passing focused validation.
