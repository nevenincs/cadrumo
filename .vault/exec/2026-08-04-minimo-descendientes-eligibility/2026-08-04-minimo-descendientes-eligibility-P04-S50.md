---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:fdb6ad131d7323f0a202dc7ac6f553357727b8cf7a0b1c9e413cbba57142231a'
step_id: 'S50'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---
# Promote M100/2024 casilla 0611 to the established derived-profile-scalar registry producer, removing the manual casilla-input path and fallback while preserving revision-specific legal oracles, diagnostics, provenance, and calculate/pull convergence

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/application/modelo/_profile_binding.py`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `src/cadrumo/application/modelo/tests/`
- `src/cadrumo/domain/calculations/registry/tests/`
- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Derive the 2024 maternity deduction once from the canonical per-descendant resolution, and leave its profile fact absent when the required ceilings cannot resolve.
- Enroll the derived profile key as a `profile/copy` binding and make 0611 a computed binding-leaf formula with 2024 source citations, construct membership, and casilla provenance.
- Remove calculate-time 0611 injection while retaining the existing withheld, cotizaciones, and ambiguous-relacion advisories.
- Add real CLI proofs for the manual oracles, direct-input refusal, formula provenance, and M130 projection observation.

## Outcome

- M100/2024 casilla 0611 is produced only by the profile-derived scalar and its registered formula; neither `--casilla 0611=0` nor `--casilla 0611=9999` can overwrite it.
- The profile fold retains per-child caps: 2,400 for two ordinary twelve-month children, 1,200 for one, 600 for six months, 1,350 after qualifying alta posterior, and 2,550 for a mixed-cap pair.
- Direct registry scenarios explicitly provide the resolved zero scalar when no profile facts are in scope, matching the application resolver rather than masking a missing binding.

## Verification

- `uv run --no-sync pytest -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_maternidad_meses_reach_the_calculate_path.py src/cadrumo/entrypoints/cli/tests/test_modelo_projection.py -q`
  `31 passed in 61.49s (0:01:01)`
- `uv run --no-sync pytest -n 0 src/cadrumo/application/modelo/tests/test_maternidad_alta_posterior_resolution.py src/cadrumo/application/modelo/tests/test_maternidad_cotizaciones_ceiling.py -q`
  `10 passed in 8.77s`
- `uv run --no-sync pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_m100_2024_final_settlement_chain_wiring.py src/cadrumo/domain/calculations/registry/tests/test_modelo_100_2024_profile_surface.py -q`
  `6 passed in 13.87s`
- `uv run --no-sync pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part1.py src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part2.py -q`
  `85 passed in 20.68s`
- `uv run --no-sync ruff check src/cadrumo/application/modelo/_profile_binding.py src/cadrumo/application/modelo/_calculate_input.py src/cadrumo/application/modelo/tests/test_maternidad_alta_posterior_resolution.py src/cadrumo/application/modelo/tests/test_maternidad_cotizaciones_ceiling.py src/cadrumo/entrypoints/cli/tests/test_maternidad_meses_reach_the_calculate_path.py src/cadrumo/entrypoints/cli/tests/test_modelo_projection.py src/cadrumo/domain/calculations/registry/tests/test_m100_2024_final_settlement_chain_wiring.py`
  `All checks passed!`
- `uv run --no-sync basedpyright src/cadrumo/application/modelo/_profile_binding.py src/cadrumo/application/modelo/_calculate_input.py src/cadrumo/entrypoints/cli/tests/test_maternidad_meses_reach_the_calculate_path.py src/cadrumo/entrypoints/cli/tests/test_modelo_projection.py src/cadrumo/domain/calculations/registry/tests/test_m100_2024_final_settlement_chain_wiring.py`
  `0 errors, 0 warnings, 0 notes`

## Notes

- A first combined registry command was not evidence: it named a nonexistent path and collected zero tests under the default marker filter. The actual unit and registry selections above were run separately and passed.
- A mutation edit was not safe in this shared worktree. The non-tautological integration cases exercise distinct legal amounts, per-child cap composition, input refusal, persisted formula provenance, and the M130 pull path.
