---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-03-untangle-validate-tax-id-exec]]"
---

# 2026-04-30-aeat-restructure step-03 untangle formulas public surface

## status

Step 3 PR 2 of N — resolves layered violations 2 + 6 + 7 in one move (3 of 7 violations) by promoting 6 internal `aeat.domain.formulas` symbols to the public surface and rewriting all 14 caller import lines.

## scope

### symbols promoted to `aeat.domain.formulas` public surface

- `MODELO_100_SUMMARY_2025` (was at `formulas._rulesets`)
- `LIS_ART_12_LINEAL_TABLE`, `AssetClass` (were at `formulas._rulesets.modelo_100._amortization`)
- `CCAA`, `compute_cuota_autonomica_general` (were at `formulas._rulesets.modelo_100._ccaa`)
- `ValuationMethod` (was at `formulas._rulesets.modelo_100._inventario`)

Existing already-public symbols (no promotion needed; only import-path rewrite): `Discrepancy`, `Ruleset`, `FiscalPeriod`, `Quarter`, `get_registry`.

### caller import rewrites (14 sites)

| File | Old path (subpackage-private) | New path (public) |
|---|---|---|
| `src/aeat/domain/profile/__init__.py:15` | `..formulas._rulesets.modelo_100._ccaa` | `..formulas` |
| `src/aeat/domain/profile/assets/__init__.py:11` | `...formulas._rulesets.modelo_100._amortization` | `...formulas` |
| `src/aeat/domain/profile/assets/test_assets.py:12` | (same) | `...formulas` |
| `src/aeat/domain/profile/inventory/__init__.py:12` | `...formulas._rulesets.modelo_100._inventario` | `...formulas` |
| `src/aeat/domain/profile/inventory/test_inventory.py:13` | (same) | `...formulas` |
| `src/aeat/application/verification/_verify.py:10–11` | `..formulas._ledger` + `..formulas._ruleset` | `..formulas` |
| `src/aeat/application/verification/test_verify.py:18–19` | `..formulas._registry` + `..formulas._ruleset` | `..formulas` |
| `src/aeat/application/verification/test_verify.py:76` | `..formulas._period` | `..formulas` |
| `src/aeat/entrypoints/cli/filing/__init__.py:653–654` | `...formulas._period` + `...formulas._registry` | `...formulas` |
| `src/aeat/entrypoints/cli/filing/__init__.py:689–690` | `...formulas._rulesets` + `...formulas._rulesets.modelo_100._ccaa` | `...formulas` |

## verification

- `python -c "from aeat.domain.formulas import CCAA, LIS_ART_12_LINEAL_TABLE, MODELO_100_SUMMARY_2025, AssetClass, ValuationMethod, compute_cuota_autonomica_general"` — succeeds.
- `pytest --collect-only` — 6796/6820 tests collect; zero collection errors.
- `grep -rn "from .*formulas\\._(period|registry|ruleset|ledger|rulesets)" src/aeat/profile src/aeat/verification src/aeat/entrypoints/cli/filing` — zero remaining hits.

## findings (FIX / FILE / STRIKE)

None additional — clean batch promotion + rewrites.

## next step

Step 3 PR 3 — relocate `casillas/_test_cli.py` and `casillas/test_live_cli.py` from `aeat.domain.casillas/` to `aeat.entrypoints.cli.casillas/` (audit 18, layered violation #1 — tests reaching into entrypoint while colocated with domain).

After PR 3 ships, Step 3 covers 4 of 7 violations. Violation 3 (`filing._review` → `aeat.domain.financial.transactions._repository`) is the final substantive untangle; the remainders fold into Step 7 keystone treatment.
