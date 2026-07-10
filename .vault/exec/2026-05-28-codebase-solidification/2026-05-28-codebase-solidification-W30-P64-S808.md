---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-07-03'
modified: '2026-07-08'
step_id: 'S808'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# Migrate ValidatedRegistryAuthority.load call sites to the session authority fixture

## Scope

- `src/aeat/domain/calculations/registry/tests/test_authority.py`
- `src/aeat/domain/calculations/registry/tests/test_deduccion_madrid_nacimiento_adopcion.py`
- `src/aeat/domain/calculations/registry/tests/test_m100_2020_estimacion_directa_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_m100_2020_rendimientos_trabajo_despido_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_m100_2024_capital_inmobiliario_arrendamiento_vivienda_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_m100_2024_estimacion_directa_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_m100_2024_ganancias_patrimoniales_transmision_inmueble_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_m100_2024_rendimientos_trabajo_despido_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_m100_rental_reduccion_art23_2.py`
- `src/aeat/domain/calculations/registry/tests/test_m303_2024_regimen_general_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_m322_2024_grupo_entidades_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_m353_2024_grupo_entidades_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_m390_2024_annual_manual_worked_example.py`
- `src/aeat/domain/calculations/registry/tests/test_modelo_100_imputed_real_estate_art85.py`

## Description

- Enumerate the direct `ValidatedRegistryAuthority.load` call sites under the
  registry tests tree and classify each: bundled-authority loads (migrate) vs
  the negative-path caching / fingerprint / error-path tests that build a
  registry under `tmp_path` (leave).
- Confirm `resources().modelos.authority` (the `registry_authority` session
  fixture), `bundled_authority()`, and the direct bundled `.load(...)` all
  resolve to the identical cached instance, so the migration is
  behaviour-preserving.
- Migrate the ten manual-grounding test functions and the two module-scoped
  authority/snapshot fixtures to consume the session `registry_authority`
  fixture instead of a per-call `.load(...)`.
- Migrate the `@cache` `_authority()` helper in the imputed-real-estate test to
  `bundled_authority()`, dropping the inline bundled-path boilerplate.
- Route the one positive-cluster `.load(...)` in `test_authority.py` through the
  existing module `_packaged_authority` fixture, matching its sibling tests.
- Remove the now-dead `_REGISTRY_ROOT` / `_SOURCE_ROOT` module constants and the
  orphaned `bundled_path` import from the files where they were only feeding the
  migrated `.load(...)`; retain them where the scenario harness still consumes
  them.

## Outcome

- 61 tests across the migrated files pass; `test_authority.py` negative-path
  caching/fingerprint/error tests remain on their `tmp_path` loads and stay
  green (13 in that file plus the reverted grounding file).
- Behaviour preserved: the session fixture is the same authority object the
  removed `.load(...)` produced, so snapshots and verification policies are
  identical.
- A mutation probe negated the grounding-membership assertion in the M303
  grounding test; it failed as required, confirming the assertion reads real
  registry data through the fixture and is not tautological.
- Ruff clean; long grounding-test signatures wrapped to satisfy the line-length
  gate.

## Notes

- The per-call `.load(...)` re-fingerprints the registry tree on every call even
  though the compiled result is LRU-cached; the session fixture eliminates that
  per-file re-fingerprint. Negative-path tests that assert the load/cache
  mechanism itself were intentionally not migrated.
- Left every secure-storage fixture untouched (deferred S804) and made no change
  to `pyproject.toml` addopts (deferred S809).
