---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S2308'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
---

# `cli-workflow-redesign` `W84.P405.S2308`

Completed the corrective application foreign-assets aggregation slice for Modelo 720.

- Modified: `src/aeat/application/aggregation/_foreign_assets.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `src/aeat/application/aggregation/test_foreign_assets.py`

## Description

Baseline verification found the plan row already checked, but the implementation only partially satisfied the row: `ForeignAssetObservation` rejected bare `invoice` while still accepting arbitrary noncanonical source kinds, rollups merged source-kind cohorts for the same asset class, the public aggregation package did not export the Modelo 720 asset aggregation API, and no S2308 execution record existed.

The implementation now enforces the four-source taxonomy exactly at the application aggregation boundary: `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`. Conceptual asset-source labels such as `foreign_account_statement` are rejected rather than normalized or shimmed.

Foreign asset rollups now carry `source_kind` and aggregate by `(source_kind, asset_class)`, preventing purchase evidence and payable invoice cohorts from being silently merged. The Modelo 720 threshold helpers now evaluate a full `ForeignAssetsAggregation`, so source-kind cohort splitting cannot under-declare an asset class whose total crosses the €50,000 floor. The public `aeat.application.aggregation` package now exports the Modelo 720 aggregation models and functions.

Final review found that public `ForeignAssetClassRollup` instances did not validate the `countries` tuple, and country validation relied on Python Unicode `isalpha()`. Rollups now validate every country value as ASCII ISO alpha-2, matching observation validation.

Registry TOML expansion was not included in this corrective app slice. Current `registry/aeat/modelos/720.toml` remains manual-input/layout oriented, and adding new 720 binding declarations requires a concrete registry binding contract rather than a placeholder source.

## Tests

Focused verification passed:

- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_foreign_assets.py`
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_counterpart.py src/aeat/application/aggregation/test_foreign_assets.py`
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_counterpart.py src/aeat/application/aggregation/test_foreign_assets.py src/aeat/application/aggregation/test_retenciones.py` passed 78 tests
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_foreign_assets.py src/aeat/domain/calculations/registry/test_modelo_720_registry.py` passed 46 tests
- `uv run --no-sync pytest --collect-only -q src/aeat/application/aggregation` collected 171 tests
- `uv run --no-sync ruff check src/aeat/application/aggregation/_counterpart.py src/aeat/application/aggregation/test_counterpart.py src/aeat/application/aggregation/_foreign_assets.py src/aeat/application/aggregation/test_foreign_assets.py src/aeat/application/aggregation/__init__.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --json`
- `git diff --check -- src/aeat/application/aggregation/_counterpart.py src/aeat/application/aggregation/test_counterpart.py src/aeat/application/aggregation/_foreign_assets.py src/aeat/application/aggregation/test_foreign_assets.py src/aeat/application/aggregation/__init__.py`
