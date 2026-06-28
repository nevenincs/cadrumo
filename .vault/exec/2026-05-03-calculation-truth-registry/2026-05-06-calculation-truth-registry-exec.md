---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `renta local scenario verification`

Added a registry-native local scenario verification harness for Renta
calculation hardening.

- Created: `src/aeat/domain/calculations/registry/_scenarios.py`
- Created: `src/aeat/domain/calculations/registry/test_registry_scenarios.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Modified: `.vault/adr/2026-05-03-calculation-truth-registry-pending-adr.md`
- Created: `.vault/audit/2026-05-06-calculation-truth-registry-review.md`

## Description

The registry now has a local scenario harness that runs curated assumptions
through the validated snapshot calculator and compares exact expected casilla
values, operand traces, legal references, and source references. This fills the
gap between isolated formula tests and workbook/live parity: scenarios are
local, deterministic, and can encode known outcomes even when an official
executable oracle is unavailable or delayed.

The harness binds the scenario's declared modelo revision during snapshot
selection. A scenario that claims an incompatible revision now fails before
calculation instead of silently running the filing-year default.

The Modelo 100 scenario coverage exercises ejercicio 2025 normal direct
estimation with payments on account, simplified direct estimation with the
EUR 2,000 difficult-justification cap, and a negative simplified-estimation
base that must clamp difficult-justification expenses to zero. A negative
scenario test proves that trace-contract drift is reported as a mismatch even
when the numeric value still matches.

The scenario matrix now also covers real-estate capital rollups and final
settlement rollups. The real-estate scenario checks net capital-inmobiliario
return, reduced return, imputed-rent passthrough, reduced-return total, and
rental withholding propagation. The final-settlement scenario checks cuota
liquida incrementada total, cuota resultante de autoliquidacion, total pagos a
cuenta, cuota diferencial, and resultado de la declaracion.

The Renta WEB Open oracle adapter now has a guarded result path. Without a
configured live driver it returns `unverifiable` after remote-state guard
preflight. With the local replay driver it compares captured observed casilla
values against expected values and returns structured `match`, `mismatch`, or
`unverifiable` `ParityResult` records. Guard refusals return `blocked` before
driver execution.

The Renta WEB Open live calculation checker now also opens the current
anonymous 2025 Open simulator on `www2.agenciatributaria.gob.es`, fills a valid
synthetic personal profile, scrapes summary calculation outputs, and compares
them through `ParityResult`. The 2026-05-06 `live_read` run matched AEAT for
resultado de la declaracion, minimo personal/familiar estatal y autonomico, and
cuota diferencial.

This does not close the broader Renta verification row. Official/manual
examples beyond the baseline Renta WEB Open profile, CCAA variation, rental-ledger row
providers, amortization/inventory provider linkage, objective-estimation
modules, and downstream workflow linkage remain open.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_scenarios.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_modelo_100_direct_estimation_net_returns_and_reductions_branch_on_mode_binding src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_modelo_100_simplified_direct_estimation_difficult_justification_cap_is_registry_backed`
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_scenarios.py src/aeat/domain/calculations/registry/test_registry_scenarios.py src/aeat/domain/calculations/registry/__init__.py`
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_scenarios.py src/aeat/domain/calculations/registry/test_registry_scenarios.py src/aeat/domain/calculations/registry/__init__.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_scenarios.py src/aeat/domain/calculations/registry/test_modelo_100_parity_tapes.py src/aeat/domain/calculations/registry/test_parity_tapes.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py`
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_renta_web_open_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py`
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_renta_web_open_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py`
- `uv run --no-sync vaultspec-core vault check all`

The vault-wide check still fails on pre-existing structure and dangling-link
debt across the vault. Frontmatter, links, body links, references, and schema
checks are clean.
