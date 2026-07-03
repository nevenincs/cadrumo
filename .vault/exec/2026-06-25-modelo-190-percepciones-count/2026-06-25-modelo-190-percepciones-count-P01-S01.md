---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S01'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Verify the pull and import path populates clave on every WithholdingObservation row

## Scope

- `src/aeat/application/aggregation`

## Description

- Ground current implementation with `uvx vaultspec-rag search "modelo 190 percepciones count withholding source current plan P01 P05" --type code`.
- Inspect the typed withholding observation model and the CLI producer/store path.
- Run the producer test file with the new clave-less refusal gate included.

## Outcome

- `WithholdingObservation.clave` is required and typed as `RetencionClave`; it has no default value and no clave-less fallback.
- The CLI producer parses `--withholding-observation` JSON through `_parse_typed_cli_observations`, materialises typed `WithholdingObservation` rows, and persists the same set through `persist_withholding_observations`.
- `test_parse_withholding_observation_from_cli_json` proves the producer accepts clave/subclave-bearing rows, and `test_persisted_withholding_set_is_readable_by_the_store` proves the store later read by the resolver receives the same typed rows.
- Verification passed in `uv run --no-sync pytest -q --tb=short src/aeat/entrypoints/cli/tests/test_withholding_producer.py`: 4 passed.

## Notes

- No production change was needed for S01. S02 adds the explicit negative gate for a missing `clave`.
