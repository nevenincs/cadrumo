---
tags:
  - '#exec'
  - '#inventory-management'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-inventory-management-plan]]'
  - '[[2026-04-29-inventory-management-code-review-audit]]'
---

# `inventory-management` `implementation` summary

Implemented the first #453 tracking surface for M100 Anexo D normal inventory
and amortization inputs.

- Created: `src/aeat/domain/profile/assets/__init__.py`
- Created: `src/aeat/domain/profile/inventory/__init__.py`
- Created: `src/aeat/domain/profile/errors.py`
- Created: `src/aeat/entrypoints/cli/profile/__init__.py`
- Created: `src/aeat/entrypoints/cli/profile/assets.py`
- Created: `src/aeat/entrypoints/cli/profile/inventory.py`
- Created: `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_d_ledgers.py`
- Created: `docs/concepts/inventory-and-amortization.md`
- Modified: `src/aeat/core/errors/_registry.py`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_json_schema_conformance.py`
- Modified: `src/aeat/entrypoints/cli/workflow/test_cli.py`
- Modified: `docs/coverage/kent-capabilities.md`

## Description

The assets ledger adds strict/frozen `AssetRecord`, `AmortizationEntry`, and
`AmortizationLedger` models with schema version `1`. JSON Path A persistence
uses `~/.config/aeat/assets-ledger.json` and
`~/.config/aeat/assets-amortization-ledger.json` by default, with `storage_dir`
overrides for real-file tests. Amortization uses the existing `AssetClass` and
LIS art. 12.1.a table, prorates first-year days, rounds to cents, and enforces
cumulative cost-basis caps. Re-recording an existing asset/year is idempotent.

The inventory ledger adds strict/frozen `InventoryLedger` and `MovementRecord`
models with schema version `1`. JSON Path A persistence uses
`~/.config/aeat/inventory-ledger.json`. The v1 model refuses LIFO at parsing,
stores the legal valuation method, and computes signed `0155` as closing stock
minus opening stock from explicit closing stock or signed movements. Full
method-specific layer valuation is scheduled for the continuation persistence
and UX audit because it requires opening quantities and stock layers.

The M100 helper `derive_anexo_d_normal_inputs` preserves backwards
compatibility: caller-supplied aggregates remain unchanged unless ledgers are
explicitly supplied. When supplied, inventory ledgers derive `0155` and asset
ledgers derive `0173`.

The CLI adds `aeat profile assets` and `aeat profile inventory` command groups,
including list/add/show/record commands and registered JSON schemas.

Continuation phases were added to the plan for Kent CLI UX auditing, #216
persistence-adherence auditing, and data-security opt-in/adherence support.

## Tests

Focused verification passed:

- `uv run pytest src/aeat/domain/profile/assets/test_assets.py src/aeat/domain/profile/inventory/test_inventory.py src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_d_ledgers.py src/aeat/entrypoints/cli/profile/test_profile_cli.py`
- `uv run pytest src/aeat/entrypoints/cli/test_json_schema_conformance.py src/aeat/entrypoints/cli/workflow/test_cli.py::TestWorkflowCli::test_next_json_round_trips`
- `uv run ruff check ...` on the touched slice
- `uv run ty check ...` on the touched slice

Full project verification:

- `just lint` passed.
- `just test` passed: 4,828 passed, 19 skipped, 24 deselected.
- `just typecheck` and `just hooks` still fail on unrelated branch-wide ty
  diagnostics in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py`,
  `src/aeat/domain/schema/test_cache.py`, `src/aeat/domain/schema/test_models.py`, and
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/_declarations.py`. The touched #453 slice type-checks cleanly.

Formal vaultspec code review passed after resolving all findings in
`2026-04-29-inventory-management-code-review`.
