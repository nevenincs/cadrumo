---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d383a6a0c5e461aaccefaf4c6da2d98a40446ebe4147485b24677811f06b2520'
step_id: 'S48'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Constrain Modelo 220 2025 source and selection scope to 2025 authority, remove or replace the 2026 publication-bound exception, and admit a 2026 successor only from hash-pinned exact authority without promoting authority grade.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/220/`
- `src/cadrumo/_data/registry/aeat/legal/`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Confirm the hash-pinned 2025 design and Orden HAC/529/2026 both end their
  authority at calendar 2025.
- Rename the bounded revision and its fragment directory to `2025`, then set
  matching validity and selector termini at 2025-12-31.
- Remove the Modelo 220 2026 publication-bound source exception.
- Route the source-matrix predicate through a focused M220 mutation proof.

## Outcome

Modelo 220 now selects revision `2025` for period `0A` in 2025 and refuses the
same coordinate in 2026. The revision remains `applicability` grade and
non-fileable; no 2026 successor, layout, producer, casilla surface, or grade
promotion is claimed.

`RevisionId` imposes lexical validity while the fragmented loader requires the
directory name and TOML revision key to match. The new exact selector made the
old `2025-y-siguientes` identifier false in meaning, so both were renamed in
one change with no alias or compatibility path.

The mutation proof widens the loaded 2025 selector only in memory, confirms it
would select 2026, and proves the shared source-matrix predicate refuses that
coordinate because `aeat-dr-220-2025` ends in 2025.

## Notes

- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py` passed.
- Focused source-matrix and M220 mutation tests passed (2 passed).
- Bundled catalogue validation passed (1 passed), and the Modelo 220/222
  registry suite passed (9 passed).
- A future successor requires its own exact hash-pinned AEAT design and
  approving authority before it is registered or selected.
