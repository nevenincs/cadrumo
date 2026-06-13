---
tags:
  - '#exec'
  - '#mutation-harness-fix'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-mutation-harness-fix-plan]]'
  - '[[2026-04-29-mutation-harness-fix-adr]]'
---

# exec phase3 task1 — M100 mul/div scalar fixtures

## What

`src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py`:

- Imported `MODELO_100_2024 / 2025 / 2026` and the `Iterator`
  collection ABC.
- Added three M100-archetype fixture factories:
  - `_f100_general_for_scalar()` — drives BLG into TARIFA_ESTATAL_GENERAL
    bracket 5 (60 000-300 000 € at 22.5 %); 0540 baseline
    17 950,75 €.
  - `_f100_ahorro_for_scalar_2024()` /
    `_f100_ahorro_for_scalar_post_2025()` — drives BLA into
    TARIFA_ESTATAL_AHORRO bracket 5 (>300 000 €); 2024 rate 14 %
    (0560 = 42 940 €), 2025/2026 rate 15 % (0560 = 43 440 €) per
    Ley 7/2024.
  - `_f100_art20_slope_for_scalar()` — drives 0001 = 16 000 € so
    Anexo B1 art. 20 piece_a is active (slope 1.75); 0021
    baseline 5 293 €.
- Added `_modelo_100_archetypes()` returning 9
  `(ruleset, casilla, leaf_path, fixture_factory)` entries (3
  archetypes × 3 years).
- Refactored `_build_test_params()` to layer the existing walked
  enumeration (M303 / M200 / M202) with the new selective M100
  archetype enumeration.
- Added `_iter_scalar_targets()` yielding the unique
  `(ruleset_id, casilla_id, leaf_path)` triples for the kill-rate
  aggregator.
- Added `test_m100_selective_paths_match_walker` — a sanity check
  that every declared M100 archetype path is enumerated by
  `iter_scalar_leaf_paths`.

## Why

Issue #457 scope item 1 prescribes "≥ 1 mul/div scalar fixture per
M100 year" covering one TARIFA_ESTATAL_GENERAL rate, one
TARIFA_ESTATAL_AHORRO rate, and one LIRPF art. 20 slope. The
selective enumeration is necessary because a single ruleset-wide
fixture cannot drive each of the 20 mul/div leaves per year into
its target bracket (the walked enumeration assumes a single fixture
per ruleset).

## Verification

`uv run pytest src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py -q`
→ 36 passed (was 17 pre-#457). 18 new M100 cases (9 archetypes × 2
directions) plus 1 new sanity-check test. Each M100 mutation
produces a discrepancy ≥ 0.02 € on the target casilla.
