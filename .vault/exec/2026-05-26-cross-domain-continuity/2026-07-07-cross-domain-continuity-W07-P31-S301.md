---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S301'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-01-modelo-100-minimo-descendientes-engine-adr]]"
---

# cross-domain-continuity W07.P31.S301

## Scope

- Investigate the historical claim that M100 2024 casillas `0511`, `0513`,
  `0515`, and `0517` did not consume profile family/spouse facts for ROSA-E.
- Confirm whether current code already computes the descendant minimum from
  real profile facts, or patch the smallest registry/profile surface if not.

## Grounding

- Ran `uvx vaultspec-rag search "S301 M100 2024 0511 0513 0515 0517 spouse descendientes minimo profile bindings" --type code`.
  The top hits were the current 2024 descendant-minimum bindings
  `0054-renta-2024-profile-minimo-descendientes-estatal.toml`,
  `0065-renta-2024-profile-minimo-descendientes-autonomico.toml`,
  and `src/aeat/application/modelo/_profile_binding.py`.
- Ran `uvx vaultspec-rag search "S301 cross-domain-continuity M100 2024 0511 0513 0515 0517 spouse descendientes minimo profile bindings" --type vault`.
  The vault results identified the cross-domain-continuity plan row, the
  Modelo 100 mínimo-descendientes ADR, and prior Cluster T exec/audit records.

## Findings

- S301 is superseded by later work. M100 2024 now declares
  `renta-2024-profile-minimo-descendientes-estatal` and
  `renta-2024-profile-minimo-descendientes-autonomico`, which feed formulas
  targeting casillas `0513` and `0514`.
- `src/aeat/application/modelo/_profile_binding.py` injects
  `renta_family.descendientes_minimos_aggregate_2024` and
  `renta_family.descendientes_minimos_aggregate_autonomico_2024` from real
  `renta_family.descendiente.*` profile facts before profile bindings are
  routed into the calculation engine.
- Casilla `0511` is not spouse-derived. It is the taxpayer minimum under LIRPF
  Art. 57, computed from statutory parameters plus the taxpayer birth-date
  date binding for age supplements.
- The downstream minimum-family chain for the estatal half is
  `0519 = 0511 + 0513 + 0515 + 0517`, `0521 = min(0505, 0519)`, and `0530`
  applies the escala to that minimum-family base. No spouse identity fact is a
  legal operand of those target casillas.
- Spouse facts are already profile-bound where they are relevant to the 2024
  registry surface: the declaration identity section binds spouse NIF, name,
  birth date, sex, disability grade, non-resident flag, EU/EEA flag, and EU/EEA
  country through `renta-2024-profile-spouse-*` bindings.

## Evidence Added

- Added
  `src/aeat/application/modelo/tests/test_minimo_descendientes_engine.py::test_profile_descendant_facts_feed_2024_minimo_and_downstream_tariff`.
- The test writes a real profile into the isolated encrypted runtime profile
  repository, with two `renta_family.descendiente.*` rows and Catalonia tax
  residence.
- It resolves profile-sourced bindings through the real resolver, feeds the
  resulting binding/date/enum channels into the 2024 registry calculation, and
  proves:
  - profile facts resolve `renta-2024-profile-minimo-descendientes-estatal`
    and `renta-2024-profile-minimo-descendientes-autonomico` to `7900.00`;
  - casillas `0513` and `0514` receive `7900.00`;
  - downstream cuota íntegra estatal `0545` is `3097.00`, the LIRPF 2024
    table oracle for base `35400` and total minimum `13450`.

## Verification

- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_minimo_descendientes_engine.py::test_profile_descendant_facts_feed_2024_minimo_and_downstream_tariff -q`
  passed.
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_minimo_descendientes_engine.py src/aeat/domain/calculations/registry/tests/test_modelo_100_2024_profile_surface.py src/aeat/application/modelo/tests/test_modelo_100_2024_profile_coverage.py src/aeat/domain/calculations/registry/tests/test_modelo_100_tarifa_real.py -q`
  passed with 42 tests.

## Outcome

No registry or application production patch was required. The code path is
already fixed; this step adds the missing end-to-end proof and closes the
historical S301 plan row.
