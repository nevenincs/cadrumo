---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S153'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S153 CLI Transport Registrar Split

Scope: decompose oversized CLI transport registrars without moving business logic into entrypoints.

## Description

- Split profile bundle import/export command registration into focused helpers.
- Split config repair command registration into root, logs, quarantine, reset-state, integrity, and connectivity helpers.
- Split ledger read registration by command and moved ledger review registration/rendering into `_ledger_review_cli.py`.
- Moved ledger bulk-classify transport handling into `_ledger_classify_cli.py`, leaving classification behavior in the application layer.
- Split ledger evidence registration into one-command helpers.
- Split modelo projection/compare and IVA wallet registration into focused command helpers.
- Updated repair-policy AST discovery to include `_custody_secret.py`, where the custody recovery/rekey commands now live after the earlier split.

## Outcome

No production CLI callable remains over 180 lines. The CLI modules still have legacy module-size allowances for broader monolith work (`_modelo.py`, `_config/__init__.py`, payload modules, `_app_live.py`, `_ledger.py`); those are left for the hard-budget replacement steps rather than hidden under this registrar row.

## Verification

- `uv run --no-sync ruff check` over changed CLI modules and the repair policy test.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py src/aeat/tests/test_codebase_size_budgets.py -q`
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_ledger_bulk_classify.py src/aeat/entrypoints/cli/tests/test_ledger_classify_fixture.py src/aeat/entrypoints/cli/tests/test_ledger_ux_defect_cluster.py src/aeat/entrypoints/cli/tests/test_ledger_validation_paths.py -q`
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py -q`
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_cli_surface.py -q`
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_ledger_list_filter.py src/aeat/entrypoints/cli/tests/test_modelo_projection.py src/aeat/entrypoints/cli/tests/test_modelo_compare.py src/aeat/entrypoints/cli/tests/test_repair_policy_coverage.py src/aeat/entrypoints/cli/tests/test_repair_privacy_contract.py src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py -q`
- `vaultspec-rag` code search through the resident service on port 8766 for the decomposed CLI callable surfaces.

## Notes

During verification, registry test collection exposed a concurrently broken `_validate_revision_sections.py` facade. The repair restored `validate_revision_definition` and split its per-section dispatch into focused helpers; focused registry schema and referential-integrity part tests passed after that repair.
