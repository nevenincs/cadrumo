---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S03'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---



# `registry-casilla-identity` `P01.S03`

Added a focused real-behaviour test group for the `segmento` field on
`CasillaDefinition`.

- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`

## Description

`test_registry_schema.py` gained `CasillaDefinition` to its `_schema`
import and four focused tests built on a real single-segment
`CasillaDefinition` fixture (`_single_segment_casilla`), constructed
directly with no mocks, stubs, or patches:

- `test_casilla_segmento_defaults_unset` asserts a single-segment
  casilla leaves `segmento` unset (`None`).
- `test_casilla_segmento_accepts_aeat_record_segment_code` asserts the
  field accepts a real AEAT `DP`-code string (`DP200014`).
- `test_single_segment_casilla_validates_unchanged_with_segmento_unset`
  pushes a single-segment casilla through a strict pydantic
  `model_dump` / `model_validate` round-trip, asserts strict equality
  across the boundary, asserts `segmento` stays `None`, and asserts
  `segmento` is absent from `model_dump(exclude_defaults=True)` —
  proving the field is purely additive for the ~25 single-segment
  modelos.
- `test_casilla_segmento_rejects_empty_string` asserts an empty
  `segmento` is rejected by the `min_length=1` bound, keeping "unset"
  distinct from "empty".

Each test would fail if the additive `segmento` field were absent,
mistyped, or non-defaulting, so none is tautological.

## Description (collision)

The shared-worktree collision check (`git diff` against
`test_registry_schema.py`) returned clean before the edit; no
non-authored uncommitted WIP was present.

## Tests

`uv run --no-sync ruff check` on `test_registry_schema.py` passed. The
four new tests passed in isolation, and the full
`test_registry_schema.py` module passed at 70 tests (66 pre-existing +
4 new) against the bundled registry corpus with real adapters and no
mocks, skips, or xfail markers.
