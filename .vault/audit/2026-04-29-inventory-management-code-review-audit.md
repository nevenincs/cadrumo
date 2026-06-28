---
tags:
  - '#audit'
  - '#inventory-management'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-inventory-management-research]]'
  - '[[2026-04-29-inventory-management-adr]]'
  - '[[2026-04-29-inventory-management-plan]]'
---

# `inventory-management` Code Review

Status: PASS

Scope reviewed: `src/aeat/domain/profile/**`, `src/aeat/entrypoints/cli/profile/**`, `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_d_ledgers.py`, `src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_d_ledgers.py`, `src/aeat/entrypoints/cli/__init__.py`, `src/aeat/core/errors/_registry.py`, `src/aeat/entrypoints/cli/test_json_schema_conformance.py`, `src/aeat/entrypoints/cli/workflow/test_cli.py`, `docs/concepts/inventory-and-amortization.md`, `docs/coverage/kent-capabilities.md`, and the feature vault artifacts.

Verification run: `uv run --no-sync pytest src/aeat/domain/profile/assets/test_assets.py src/aeat/domain/profile/inventory/test_inventory.py src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_d_ledgers.py src/aeat/entrypoints/cli/profile/test_profile_cli.py src/aeat/entrypoints/cli/test_json_schema_conformance.py -q` passed, 45 tests.

Re-audit verification run: `uv run --no-sync pytest src/aeat/domain/profile/assets/test_assets.py src/aeat/domain/profile/inventory/test_inventory.py src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_d_ledgers.py src/aeat/entrypoints/cli/profile/test_profile_cli.py src/aeat/entrypoints/cli/test_json_schema_conformance.py -q` passed, 46 tests. `uv run --no-sync ruff check src/aeat/profile src/aeat/entrypoints/cli/profile src/aeat/domain/formulas/_rulesets/modelo_100/anexo_d_ledgers.py src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_d_ledgers.py src/aeat/entrypoints/cli/test_json_schema_conformance.py` passed. `uv run --no-sync ty check src/aeat/profile src/aeat/entrypoints/cli/profile src/aeat/domain/formulas/_rulesets/modelo_100/anexo_d_ledgers.py src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_d_ledgers.py src/aeat/entrypoints/cli/test_json_schema_conformance.py` passed.

Final re-audit verification run: `uv run --no-sync pytest src/aeat/domain/profile/assets/test_assets.py src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_d_ledgers.py src/aeat/entrypoints/cli/profile/test_profile_cli.py -q` passed, 17 tests. `uv run --no-sync ruff check src/aeat/domain/profile/assets src/aeat/domain/formulas/_rulesets/modelo_100/anexo_d_ledgers.py src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_d_ledgers.py src/aeat/entrypoints/cli/profile` passed. `uv run --no-sync ty check src/aeat/domain/profile/assets src/aeat/domain/formulas/_rulesets/modelo_100/anexo_d_ledgers.py src/aeat/domain/formulas/_rulesets/modelo_100/test_anexo_d_ledgers.py src/aeat/entrypoints/cli/profile` passed. Manual immutability probe confirmed `AmortizationLedger.entries` is a tuple and `AmortizationEntry` rejects field assignment.

INV-001 | HIGH | RESOLVED | Re-recording an amortization year can erase valid recorded amortization

`record_amortization` computes the new year amount from a ledger whose cumulative total already includes the same target year, then overwrites `by_year[year]` with that reduced amount at `src/aeat/domain/profile/assets/__init__.py:179` and `src/aeat/domain/profile/assets/__init__.py:183`. For a libertad asset already recorded at full basis, a second record call computes `0.00` at `src/aeat/domain/profile/assets/__init__.py:150` through `src/aeat/domain/profile/assets/__init__.py:164` and persists `0.00`, deleting the prior valid deduction. The same pattern can understate the final year of a normal asset. This violates the basis-cap and persistence integrity expectations; re-recording should be idempotent or should exclude the target year from cumulative basis before replacing it.

Re-audit: resolved. `record_amortization` now returns the existing ledger unchanged when the asset/year already exists, and `test_record_amortization_is_idempotent_for_existing_year` covers the libertad full-basis regression.

INV-002 | HIGH | RESOLVED | Movement-derived inventory does not implement distinct FIFO/PMP valuation

The inventory helper exposes FIFO, PMP, and coste medio, but `_derive_pmp_closing` delegates directly to `_derive_fifo_closing` at `src/aeat/domain/profile/inventory/__init__.py:205` and `src/aeat/domain/profile/inventory/__init__.py:206`. `_derive_fifo_closing` subtracts caller-supplied COGS movement value at `src/aeat/domain/profile/inventory/__init__.py:195` through `src/aeat/domain/profile/inventory/__init__.py:202` instead of deriving issue cost from FIFO layers, and the model lacks opening quantity/layers needed to compute FIFO or weighted average from movements. This does not satisfy the plan item to compute FIFO, PMP, and coste medio variation when `closing_stock` is absent; either require explicit closing stock/COGS valuation for this release or add the quantity/layer data needed for real method-specific valuation.

Re-audit: resolved for v1 scope. Research, ADR, concept docs, and code now explicitly describe v1 movement-derived closing as opening stock plus signed movement values for all legal methods, with full stock-layer valuation deferred to the scheduled continuation audits.

INV-003 | MEDIUM | RESOLVED | The frozen amortization ledger remains mutable through nested dicts

`AmortizationLedger` is declared with `ConfigDict(strict=True, frozen=True, extra="forbid")`, but `entries` is a mutable `dict[str, dict[int, Decimal]]` at `src/aeat/domain/profile/assets/__init__.py:49` through `src/aeat/domain/profile/assets/__init__.py:55`. Pydantic frozen models prevent field assignment, not mutation of nested dictionaries, so callers can mutate `ledger.entries` after validation and bypass the intended frozen-model invariant. Use immutable ledger entries or normalize through a frozen record tuple before claiming strict frozen persistence semantics.

Re-audit: resolved. `AmortizationLedger.entries` now stores `tuple[AmortizationEntry, ...]`, and each `AmortizationEntry` is strict, frozen, and `extra="forbid"`, removing the nested mutable dictionary escape hatch.

INV-004 | LOW | RESOLVED | Document-level schema versions are not validated on load

`AssetsLedgerDocument` and `InventoryLedgerDocument` carry `schema_version` fields at `src/aeat/domain/profile/assets/__init__.py:65` through `src/aeat/domain/profile/assets/__init__.py:70` and `src/aeat/domain/profile/inventory/__init__.py:77` through `src/aeat/domain/profile/inventory/__init__.py:82`, but unlike the record models they do not validate that the document version equals `SCHEMA_VERSION` before `load_assets` or `load_inventory` accepts the file. This weakens the Path A schema-versioning contract and future #216 migration boundary.

Re-audit: resolved. `AssetsLedgerDocument` and `InventoryLedgerDocument` now validate `schema_version` with the same `SCHEMA_VERSION` guard used by the record models.

Passed invariants: `AssetClass` and `ValuationMethod` are reused; LIFO has an explicit refusal path and registered error code; representative BOE LIS art. 12.1.a coefficients include industrial buildings at 3 percent; inventory variation is signed closing minus opening; the Anexo D helper preserves caller aggregates unless ledgers are supplied; Path A JSON persistence is present; multi-actividad filtering/allocation has coverage; profile error codes are registered; profile JSON schemas are registered for the implemented JSON-output commands; new test modules have module-level markers; no new mocks, skips, or xfails were introduced in the reviewed feature tests; continuation audit loops are scheduled in the plan for Kent UX, #216 persistence adherence, and data-security opt-in/adherence support.
