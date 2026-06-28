---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P301.S1803'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w61-p301-s1801-ledger-storage-ownership-audit]]"
---

# `cli-workflow-redesign` `W61.P301.S1803`

Closed plan rows:

- `W61.P301.S1803`

## Description

Implemented the application-layer resolver that binds transaction catalogue reads and writes to the active profile bucket.

`aeat.application.workflow.active_transaction_catalogue_repository(state, objects=...)` now resolves the active bucket through the existing typed `active_bucket_id_or_raise(state)` backend helper and returns a `TransactionCatalogueRepository` bound to that bucket. The CLI no longer builds the transaction catalogue repository directly from its own bucket-resolution logic; `entrypoints/cli/_common.py` delegates to the backend resolver and only maps the typed `NoActiveProfileError` into the existing CLI error surface.

Added real storage coverage using `SecureObjectRepository` over a temporary SQLite database with an ephemeral master key. The test writes a transaction catalogue through one active profile bucket and verifies a second active profile bucket remains empty, proving the resolver routes through the actual encrypted storage backend rather than a disconnected interface.

The encrypted ledger import CLI test now creates an active profile bucket before import and reads the resulting catalogue from that same bucket. This removes the stale global-catalogue test assumption.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/workflow/_models.py`
- `src/aeat/application/workflow/__init__.py`
- `src/aeat/application/workflow/test_transaction_catalogue_resolution.py`
- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/entrypoints/cli/test_workflow_surface.py`

## Tests

- `uv run pytest src/aeat/application/workflow/test_transaction_catalogue_resolution.py src/aeat/domain/transactions/test_catalogue.py -q`
- `uv run pytest src/aeat/entrypoints/cli/test_workflow_surface.py -q`
