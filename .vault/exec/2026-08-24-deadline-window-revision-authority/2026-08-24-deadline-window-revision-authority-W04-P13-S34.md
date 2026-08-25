---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:101f3dcb686d2ccf46a9383bcdda97c8b71ad600d370c46667a22a7b7d214119'
step_id: 'S34'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Run exact historical engine and CLI scenarios for every repaired modelo against the adjudicated registry census

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_modelo_*_registry.py`
- `src/cadrumo/domain/deadlines/tests/test_engine.py`
- `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py`
- `.vault/audit/`

## Description

- Use Vaultspec RAG first to locate the existing historical registry, engine fleet, real CLI, semantic-coordinate, applicability, and supported-year authorities.
- Run the exact registry modules for every modelo in the repaired/adjudicated census: 111, 115, 123, 130, 131, 190, 193, 202, 210, 216, 303, 322, 349, 353, and 369.
- Repair the stale M322 test-only attribute access by calling the existing singular `deadline_semantic_coordinate` resolver; do not expand an unqualified base window into eleven coordinates: one unqualified base identity plus ten qualified result identities.
- Run the engine fleet invariant for both quarterly and monthly IVA profiles across the canonical supported-year catalogue.
- Run the real CLI calendar comparison across the same supported-year catalogue, sharing one transient `today_madrid()` sample between the command clock and expected application projection.

## Outcome

The historical repaired-model registry matrix passes exactly, and the canonical registry-to-engine-to-real-CLI projection remains multiplicity preserving across every supported filing year. No production resolver, date catalogue, supported-year range, modelo roster, cadence map, or deduplication path was introduced.

## Verification

- `uv run ruff check src/cadrumo/domain/calculations/registry/tests/test_modelo_322_registry.py` - passed.
- Focused M322 registry module - 15 passed in 43.36 seconds.
- Fifteen repaired-model registry modules - 235 passed in 52.89 seconds.
- Canonical engine fleet scenario, both IVA profiles - 2 passed in 40.86 seconds.
- Real CLI supported-year calendar parity scenario - 1 passed in 232.85 seconds.

## Notes

The registry census remains the date authority. The CLI scenario samples Madrid "today" once per execution because today, yesterday, and tomorrow are transient relationships; the sampled value synchronizes actual and expected execution only and is not recorded as a durable deadline fact. The first consumer command used an incorrect test node/marker combination and deliberately reported zero tests; it was rerun with the correct canonical node, producing the green engine evidence above.
