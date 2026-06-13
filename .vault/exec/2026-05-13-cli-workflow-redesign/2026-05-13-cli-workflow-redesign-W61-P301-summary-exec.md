---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P301'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w61-p301-s1801-ledger-storage-ownership-audit]]"
---

# `cli-workflow-redesign` `W61.P301`

Closed plan rows:

- `W61.P301.S1801`
- `W61.P301.S1802`
- `W61.P301.S1803`
- `W61.P301.S1804`
- `W61.P301.S1805`
- `W61.P301.S1806`

## Description

Closed the ledger bucket storage review phase.

The transaction catalogue repository is bucket-bound, active workflow state resolves transaction catalogue repositories through the active profile bucket, imported rows produce bucket-qualified transaction refs, review projections load only the requested bucket's catalogue, and ledger storage errors/log fields identify the bucket-scoped storage boundary.

The phase review found no remaining no-argument `TransactionCatalogueRepository()` constructors in the audited source slice and no remaining `aeat review show` legacy root wording in that slice. The global error registry is also clean: every registered code maps to one concrete `AeatError` subclass, and no registered orphan rows remain.

## Modified Paths

- `.vault/audit/2026-05-13-cli-workflow-redesign-W61-P301-code-review-audit.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-05-13-cli-workflow-redesign-W61-P301-S1803-exec.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-05-13-cli-workflow-redesign-W61-P301-S1804-exec.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-05-13-cli-workflow-redesign-W61-P301-S1805-exec.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-05-13-cli-workflow-redesign-W61-P301-S1806-exec.md`
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/review/test_adapters.py`
- `src/aeat/application/workflow/_models.py`
- `src/aeat/application/workflow/__init__.py`
- `src/aeat/application/workflow/test_transaction_catalogue_resolution.py`
- `src/aeat/adapters/outbound/google/__init__.py`
- `src/aeat/core/errors/registry/_adapters.py`
- `src/aeat/core/errors/registry/_domain.py`
- `src/aeat/core/i18n/_render.py`
- `src/aeat/domain/transactions/_errors.py`
- `src/aeat/domain/transactions/_models.py`
- `src/aeat/domain/transactions/_repository.py`
- `src/aeat/domain/transactions/__init__.py`
- `src/aeat/domain/transactions/test_repository.py`
- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_workflow_surface.py`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/hu.yml`

## Tests

- `uv run pytest src/aeat/domain/transactions/test_repository.py src/aeat/application/workflow/test_transaction_catalogue_resolution.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/application/review/test_adapters.py src/aeat/application/review/test_aggregator.py -q`
- `uv run pytest src/aeat/entrypoints/cli/test_workflow_surface.py -q`
- `uv run pytest src/aeat/domain/transactions/test_repository.py -q`
- `uv run pytest src/aeat/core/errors/test_registry_enforcement.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/entrypoints/cli/test_error_boundary_integration.py -q`
- `uv run pytest src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/entrypoints/cli/test_windows_encoding.py -q`
