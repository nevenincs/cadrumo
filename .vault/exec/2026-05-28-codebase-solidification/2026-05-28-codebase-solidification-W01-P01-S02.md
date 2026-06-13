---
step_id: S02
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S02 — TaxationComparisonError registry test

## Outcome

Added `test_taxation_comparison_error_is_registered_and_envelopes` to
`src/aeat/application/modelo/test_taxation_comparison.py`.

The test asserts:
- `get_registered_error_code(TaxationComparisonError)` returns an `ErrorCode`
  whose `.code` is present in `ERROR_REGISTRY`.
- The stable code string equals `"REFUSED_TAXATION_COMPARISON"` (derived from
  the registry declaration, not hand-computed).
- `build_error_envelope(exc)` produces an `ErrorEnvelope` with
  `code="REFUSED_TAXATION_COMPARISON"`, `category="REFUSED"`,
  `retryable=False`, `schema_version="1"`.

No mocks, no skips, no xfail. Uses real `build_error_envelope` and real
`ERROR_REGISTRY`.

## Pytest outcome

`pytest src/aeat/application/modelo/test_taxation_comparison.py -xvs`
→ 5 passed (S02 target test + 4 pre-existing tests). Pre-existing
`RegistryLoadError` on Modelo 210 in non-isolation runs traced to untracked
WIP from a concurrent campaign agent; does not affect S02.

## Files touched

- `src/aeat/application/modelo/test_taxation_comparison.py`

## Verification

`vault plan step check W01.P01.S02` applied after commit.
