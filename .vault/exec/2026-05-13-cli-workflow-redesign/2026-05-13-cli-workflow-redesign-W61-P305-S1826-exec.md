---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P305.S1826'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p305-s1826-code-review-audit]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-profile-output-language-adr]]"
---

# `cli-workflow-redesign` `W61.P305.S1826`

Closed plan rows:

- `W61.P305.S1826`

## Description

Exposed bucket-scoped ledger read, list, status, and provenance tracking commands under `aeat app ledger`.

The CLI now provides `aeat app ledger list`, `aeat app ledger read`, `aeat app ledger status`, and `aeat app ledger track`. These commands keep `ledger_transaction` movement facts separate from review workflow state. `read` returns one transaction from the active profile bucket. `track` returns event and provenance lineage, including `created_event_id`, evidence provenance, edit lineage, lifecycle state, and lifecycle lineage.

The command handlers remain thin. They resolve the active transaction repository with `_tx_repo(_state())`, delegate reads and summaries to `get_manual_transaction`, `list_manual_transactions`, `ledger_transaction_review_status`, and `summarize_manual_transactions`, and render through `_emit`.

The backend gained `LedgerStatusReport` and `summarize_manual_transactions` for active-bucket ledger state. Status reports count lifecycle state, active-row review readiness, optional period preflight checks, readiness issue counts, and the final readiness boolean.

The existing `aeat app ledger review` command was kept as an inspection surface and now uses the same backend read/list/status helpers instead of workflow-state review overlays for durable row facts.

The operator-surface help now advertises `list`, `read`, `status`, and `review`, with no public `ledger edit` ghost entry. Locale files carry the new ledger keys and the aggregation keys required by the current codebase. Output-language resolution follows the accepted profile-language contract: `AEAT_OUTPUT_LANGUAGE`, active profile `output.language`, then Spanish settings default.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1826-code-review-audit.md`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/application/operator_surface/_help.py`
- `src/aeat/core/config.py`
- `src/aeat/core/errors/_registry.py`
- `src/aeat/core/i18n/_render.py`
- `src/aeat/core/i18n/test_output_language.py`
- `src/aeat/entrypoints/cli/__init__.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_cli_surface.py`
- `src/aeat/entrypoints/cli/test_profile_output_language.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Tests

- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/core/i18n/_render.py src/aeat/core/i18n/test_output_language.py src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/core/config.py src/aeat/core/errors/_registry.py src/aeat/application/operator_surface/_help.py src/aeat/application/operator_surface/test_contract.py src/aeat/locales/test_parity.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/core/i18n/_render.py src/aeat/core/i18n/test_output_language.py src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/core/config.py src/aeat/core/errors/_registry.py src/aeat/application/operator_surface/_help.py src/aeat/application/operator_surface/test_contract.py src/aeat/locales/test_parity.py`
  - All checks passed
- `uv run --no-sync python -m aeat.locales audit`
  - `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/application/ledger/test_preflight.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/core/i18n/test_output_language.py src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/application/operator_surface/test_contract.py src/aeat/application/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py src/aeat/locales/test_parity.py -q`
  - 84 passed

Coverage includes real CLI initialization, manual ledger creation in the active profile bucket, `list`, `read`, `status --period`, `track`, review readback, backend ledger status/preflight services, profile-owned output language precedence, operator-surface help, and locale parity.

## Review

Formal code review initially found four S1826 issues: missing `aeat app ledger read`, English fallback in output-language resolution, incomplete fail-soft language lookup around unreadable workflow state, and locale parity drift.

All four findings were resolved. Re-review reported no remaining S1826-scope findings in `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1826-code-review-audit.md`.

## Outcome

`W61.P305.S1826` is complete. The ledger command surface now supports bucket-scoped `ledger_transaction` read, list, status, and provenance tracking flows under `aeat app ledger`, with application-service delegation, locale parity, and passing focused validation.
