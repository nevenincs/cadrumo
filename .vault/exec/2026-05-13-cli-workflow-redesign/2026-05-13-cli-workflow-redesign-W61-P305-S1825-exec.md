---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P305.S1825'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p305-s1825-code-review-audit]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
---

# `cli-workflow-redesign` `W61.P305.S1825`

Closed plan rows:

- `W61.P305.S1825`

## Description

Exposed manual transaction creation through `aeat app ledger create`.

The command creates bucket-scoped manual ledger transactions against the active profile bucket. The CLI resolves the active transaction repository with `_tx_repo(current_state)`, uses that repository's bucket id, builds a `ManualLedgerTransactionCommand`, and delegates persistence to `create_manual_transaction`.

The command accepts transaction date, amount, direction, description, optional value date, currency, counterparty, classification, business percentage, category, taxable base, IVA rate and amount, IRPF category, usage-ratio id, prorrata reference, purchase invoice evidence id, attachment ids, notes, actor, and idempotency key.

The response includes `bucket_id`, `transaction_id`, `bucket_event_ids`, and a transaction payload containing aggregation-visible tax and provenance fields. Backend persistence remains bucket-owned: the service persists through the bucket repository, verifies purchase invoice evidence and usage-ratio references, emits `LEDGER_TRANSACTION_CREATED`, saves the bucket transaction catalogue plus event, and returns emitted event ids.

The public `aeat app ledger edit` placeholder was removed during this slice because it was a registered refusal surface, not a real backend-backed command. A follow-up scan confirmed no stale edit command, locale, or error keys under CLI entrypoints or locale files. Full bucket history remains available through `aeat config bucket history`.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1825-code-review-audit.md`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_cli_surface.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Tests

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/ledger/test_actions.py -q`
  - 46 passed
- Locale YAML parse check for `src/aeat/locales/*.yml`
  - All locale files parsed

Coverage includes real CLI initialization, manual ledger transaction creation in the active profile bucket, readback through `aeat app ledger review --id`, absence of the retired `aeat app ledger edit` command, and the existing backend ledger application service tests.

## Review

Formal code review initially found one HIGH issue: public `aeat app ledger edit` remained registered as a refusal placeholder. The command, its CLI-only helpers, and stale locale keys were removed. Re-review reported no remaining blocker in `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1825-code-review-audit.md`.

Remaining open rows in this phase are `W61.P305.S1826` through `W61.P305.S1830`.
