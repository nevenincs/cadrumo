---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S371'
related:
  - '[[2026-05-26-cross-domain-continuity-plan]]'
---

# `cross-domain-continuity` `W09.P41.S371`

Flipped casilla 1812 (Ganancia no exenta imputable al ejercicio) from `input_kind = "manual"` to `"computed"` with an identity-copy formula (`op = "copy"` from 1811) in both the 2024 and 2025 M100 revisions. Added both new formula TOMLs to the ganancias-patrimoniales constructs.

- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0175-renta-2024-ganancia-cripto-imputable.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/1752-1812.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/constructs/0007-renta-2024-mini-model-ganancias-patrimoniales.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/formulas/0178-renta-2025-ganancia-cripto-imputable.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/1806-1812.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/constructs/0016-renta-2025-mini-model-ganancias-patrimoniales.toml`
- Created: `src/aeat/domain/calculations/registry/test_modelo_100_cripto_1812_propagation.py`

## Description

The root cause: casilla 1812 had no `input_kind` field (default = `"manual"`) so the engine left it at zero unless the operator explicitly duplicated casilla 1811's value via `--casilla "1812=<value>"`. Aggregators downstream (1813/1814 and the base imponible del ahorro chain) therefore silently received zero, dropping the entire crypto gain.

The fix: `op = "copy"` formula targeting 1812 with a single argument referencing 1811. AEAT form behavior for the standard single-year case is that 1812 equals 1811 (imputación total al ejercicio bajo Art. 14.1 LIRPF). Multi-year deferral under Art. 14.2.d is deferred to a future task.

The formula uses `lirpf-cuota-chain-authority` as its sole `source_refs`, consistent with the sibling formula `renta-2024-criptomonedas-ganancia-no-exenta` and with the parent construct's `source_refs`. The legal_refs anchor `ley-35-2006:art-33` (concepto ganancia patrimonial) and `ley-35-2006:art-37` (normas aplicables), matching the 1811 formula. Art. 14 (temporal imputation) is not registered as a distinct anchor in the 2024 registry; `art-33`/`art-37` cover the transmission-gain scope; temporal imputation is inherent to the copy semantics.

Both 2024 and 2025 revisions had the identical gap.

## Tests

Five regression tests in `test_modelo_100_cripto_1812_propagation.py`:

- `test_s371_2024_1812_identity_copy_standard_gain` — 1804=8500 → 1811=8500, 1812=8500.
- `test_s371_2024_1812_zero_when_no_crypto_gain` — 1804=0 → no spurious propagation.
- `test_s371_2024_1812_anti_tautology_different_gain` — 1804=7000 → 1812=7000 (different non-default, confirms wiring not cached constant).
- `test_s371_2025_1812_identity_copy_standard_gain` — 2025 revision: same identity holds.
- `test_s371_2025_1812_zero_when_no_crypto_gain` — 2025 revision: no spurious propagation.

All 5 new tests pass. All 49 existing M100 registry tests (test_modelo_100_registry, test_modelo_100_settlement_chain, test_modelo_100_drift_detection) continue to pass.
