---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S374
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` `W09.P41.S374`

M100 base imponible del ahorro chain fix (defect #181, quadruple-confirmed): added casilla `0041` (suma rendimientos reducidos del capital mobiliario) as the first summand in both the 2024 and 2025 `renta-{year}-base-imponible-del-ahorro` formula expressions. Six oracle-grounded regression tests covering four confirmed persona shapes plus anti-tautology.

- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0145-renta-2024-base-imponible-del-ahorro.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/formulas/0168-renta-2025-base-imponible-del-ahorro.toml`
- Created: `src/aeat/domain/calculations/registry/test_modelo_100_ahorro_base_chain.py`

## Description

Art. 49.1.a Ley 35/2006 (LIRPF) requires the base imponible del ahorro to include the net rendimiento del capital mobiliario (casilla `0041`). The formula chain `0027/0029→0036→0038→0040→0041` was computing correctly, but `0041` was never referenced as a summand in the `0460` formula. As a result, every M100 filer with dividends or intereses saw `0460 = 0` regardless of their capital mobiliario income.

The fix adds `{ casilla = "0041" }` as the first positional arg in the `sum` expression of both revision formulas. No other formula operands are changed. Registry referential integrity validates cleanly (35 registry tests pass).

### 2024 revision — fix

File `0145-renta-2024-base-imponible-del-ahorro.toml`: expression args before fix started with `0424`, `0429`. After fix: `0041`, `0424`, `0429`, …

### 2025 revision — same fix

File `0168-renta-2025-base-imponible-del-ahorro.toml`: identical omission; same one-line addition of `{ casilla = "0041" }`.

## Tests

Test file: `src/aeat/domain/calculations/registry/test_modelo_100_ahorro_base_chain.py`

- `test_sergio_0029_dividends_20000_populates_0460` — Sergio shape: 0029 = 20 000 EUR → 0036/0041 compute correctly → 0460 ≥ 20 000. Oracle: Art. 49.1.a LIRPF.
- `test_sergio_0460_equals_0029_when_no_losses_or_gp` — exact equality 0460 = 20 000 when no ganancias-patrimoniales or compensations. Oracle: Art. 49.1.a.
- `test_carla_0027_intereses_1200_propagates_to_0460` — Carla shape: 0027 = 1 200 EUR → 0041 = 1 200 → 0460 = 1 200.
- `test_aitor_0029_dividends_6000_populates_0460` — Aitor shape: 0029 = 6 000 EUR → 0460 = 6 000.
- `test_0460_scales_proportionally_with_capital_mobiliario_input` — anti-tautology: doubling 0029 input doubles 0460; cannot pass against a constant-0 formula.
- `test_2025_0029_dividends_20000_populates_0460` — 2025 revision guard: same chain holds after the 2025 formula fix.

All 6 tests pass (run together with `test_modelo_100_registry.py` which pre-loads the registry cache via `@cache`-decorated helpers, bypassing the peer-WIP validation collision on `renta-2024-profile-taxpayer-birth-date`).

### Pre-existing peer collision note

Peer agent WIP in the working tree (untracked: `2063-DPFNAC_D.toml`, `0007-renta-2024-profile-taxpayer-birth-date.toml`) introduces an `age_at_year_end` formula on `0511` that requires `date_binding_values`. This causes the `registry_authority` session fixture to fail validation in isolation. My tests supply `date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1975, 6, 15)}` in `_run_2024()` to satisfy the requirement. The peer WIP does not affect the capital-mobiliario chain under test.
