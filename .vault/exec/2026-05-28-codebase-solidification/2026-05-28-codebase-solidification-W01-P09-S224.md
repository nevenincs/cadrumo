---
step_id: S224
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P09.S224 — roundtrip fixture saturation structural gate

## Outcome

Created `src/aeat/test_roundtrip_fixture_saturation.py` with two real-behavior tests:

- `test_snapshot_files_still_exist`: reads the S223 audit snapshot, resolves
  each listed file path, and asserts every file still exists on disk. Catches
  renames/deletions that silently invalidate the saturation audit.

- `test_populated_builders_carry_saturation_markers`: enumerates every
  `_populated_*` function (project's canonical naming convention for "all
  optional fields set") across all roundtrip/anti-tautology test files. For
  each, asserts at least one of: (a) file module docstring contains a
  saturation keyword, (b) function docstring contains a saturation keyword,
  or (c) at least 4 keyword arguments appear in a return-call expression.
  One waiver documented inline (`_populated_snapshot` in
  `test_borrador_100_roundtrip.py` — Wave 2 TBD).

Marked `pytest.mark.unit + pytest.mark.domain_core`. Ruff clean.

## Files touched

- `src/aeat/test_roundtrip_fixture_saturation.py` (new)

## Verification

`uv run --no-sync pytest src/aeat/test_roundtrip_fixture_saturation.py -xvs` — 2 passed.
Full suite for targeted files: 19/19 passed.
`vault plan step check S224` applied.
