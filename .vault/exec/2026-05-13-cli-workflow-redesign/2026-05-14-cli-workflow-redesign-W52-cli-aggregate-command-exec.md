---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S1539-S1541-S1542-S1546-S1552-S1557-S1560'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
---

# `cli-workflow-redesign` `W52` CLI aggregate command slice

Added the thin CLI adapter for the per-modelo aggregation backend service.

- Modified: `src/aeat/entrypoints/cli/_modelo.py`
- Modified: `src/aeat/entrypoints/cli/test_modelo.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

`aeat app modelo aggregate` now accepts explicit canonical observation JSON and delegates directly to `PerModeloAggregationCommand` plus `aggregate_per_modelo`. The CLI layer only parses JSON objects and renders the backend result through `_emit`; it does not aggregate locally, does not add aliases, and does not introduce persistence or provider shims.

Added localized help text for the command and all observation options. The rendered help names only the accepted source-kind vocabulary: `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`.

Rows checked in the plan:

- `S1539` no stale CLI alias bypasses the canonical service for this surface
- `S1541` retired top-level aggregation test tree is absent; active package tests retained because they verify real aggregation behavior
- `S1542` boundary inventory records duplicate per-modelo CLI surface absence
- `S1546` command spelling and help text use the accepted surface
- `S1552` CLI behavior tests exercise the real backend service
- `S1557` CLI command delegates execution to `aggregate_per_modelo`
- `S1560` help text validates accepted vocabulary only

Rows intentionally left open:

- `S1534` and `S1550`: no persistence, bucket-event, registry provider, or adapter bridge was added.

## Tests

Focused verification passed:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_modelo.py` passed 22 tests
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_modelo.py src/aeat/application/aggregation/test_per_modelo_service.py` passed 33 tests
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_backend_boundary.py::test_per_modelo_aggregation_duplicate_cli_surfaces_stay_absent src/aeat/entrypoints/cli/test_backend_boundary.py::test_legacy_application_aggregation_test_tree_stays_absent src/aeat/entrypoints/cli/test_backend_boundary.py::test_cli_unit_tests_do_not_contain_process_state_or_xfail_language src/aeat/entrypoints/cli/test_modelo.py::test_modelo_aggregate_help_uses_accepted_source_vocabulary_only` passed 4 tests
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py`
- `git diff --check -- src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/locales/en.yml src/aeat/locales/es.yml`
