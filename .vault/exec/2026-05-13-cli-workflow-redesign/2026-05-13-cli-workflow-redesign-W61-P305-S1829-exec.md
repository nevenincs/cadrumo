---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P305.S1829'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p305-s1829-code-review-audit]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]"
  - "[[2026-05-08-cli-backend-boundary-adr]]"
---

# `cli-workflow-redesign` `W61.P305.S1829`

Closed plan rows:

- `W61.P305.S1829`

## Description

Delegated the manual ledger CLI lifecycle surface to centralized backend services and schema emitters.

`aeat app ledger import` now delegates provider resolution, validation, source ingestion, source verification, direction resolution, persistence, diagnostics, and import-batch result construction to `import_ledger_source` through `LedgerSourceImportCommand`. The CLI binds operator options, calls the backend service, and renders through `_emit`.

`aeat app ledger review` now delegates row filtering and projection to `query_ledger_review_rows` through `LedgerReviewQuery`. Backend-owned review filters include `period`, `status`, `issue`, `import`, and optional `transaction_id`. The `transaction_id` predicate intersects with the other filters instead of overriding them.

Review period filtering now uses backend `Period` parsing for `YYYY`, `YYYY-MM`, `YYYYQn`, and `YYYY-Qn`.

Import diagnostics are persisted as `LEDGER_IMPORT_DIAGNOSTIC_RECORDED` bucket events and drive `issue=` and `import=` review filtering. File-level diagnostics such as `gap` are recorded against batch transaction ids so review can return inspectable rows while durable facts remain bucket-scoped ledger transactions.

`aeat app ledger review --id` now renders an empty filtered result through `_emit` when filters exclude the requested id instead of raising `IndexError`.

`aeat app ledger export` now uses `--export-format` for artifact serialization. Root `--format` remains the command-output rendering selector.

No command-local `--json` options or legacy ratio aliases were found in the S1829 ledger CLI surface. Ledger CLI emissions route through `_emit`.

## Modified Paths

- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/domain/buckets/_event.py`
- `src/aeat/domain/buckets/test_event_catalogue.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_backend_boundary.py`
- `src/aeat/entrypoints/cli/test_cli_surface.py`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/hu.yml`

## Tests

- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_cli_surface.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_backend_boundary.py -q`
  - 80 passed
- `uv run --no-sync python -m aeat.locales audit`
  - `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` passed

Coverage includes real backend import delegation, review filtering through the application service, quarter and month period semantics, diagnostic-backed `issue=` and `import=` filters, `transaction_id` intersection behavior, empty filtered `review --id` rendering, export serialization vocabulary, backend boundary inventory, bucket event catalogue coverage, and locale parity.

## Review

Formal code review recorded S1829-001 through S1829-006 in `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1829-code-review-audit.md`.

The remediation rounds moved review filtering and projection out of the CLI, renamed export serialization to `--export-format`, centralized import source handling, added backend period parsing, persisted import diagnostics as bucket events, made `transaction_id` intersect with the other review filters, and fixed empty filtered `review --id` rendering.

Final targeted review appended `S1829-REVIEW-004 | INFO | Final S1829 remediation review clean` to the audit log.

## Outcome

`W61.P305.S1829` is complete. Manual ledger import, review, export, and scoped emission behavior now follow the backend-boundary and output-rendering ADRs: command handlers bind operator input, backend services own ledger behavior for the active profile bucket, schema emitters own payload shape, and root `--format` remains the only command-output rendering selector.
