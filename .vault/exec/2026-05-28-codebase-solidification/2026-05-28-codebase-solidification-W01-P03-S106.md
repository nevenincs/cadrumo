---
step_id: S106
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S106 — profile diagnostics unset placeholder tests

## Outcome

Extended `src/aeat/diagnostics/test_profile.py`:

- Updated two existing tests (`test_profile_unset_explicit_profile_...` and
  `test_profile_unset_uses_canonical_case_insensitive_key`) to assert against
  `_unset_placeholder()` (locale authority) rather than the hardcoded `"<unset>"` literal.
- Added `test_profile_get_unset_value_emits_localized_placeholder`: invokes
  `profile get identity.surnames` on a minimal seeded profile (surnames absent),
  asserts `identity.surnames\t{_unset_placeholder()}` in output.
- Added `test_profile_unset_emits_localized_placeholder`: unsets `identity.name`,
  asserts the localized placeholder appears in the confirmation line.

`_unset_placeholder()` resolves `tr("cli.diagnostics.profile.unset_placeholder")`
at call time to avoid import-time storage lookups.

## Files touched

- `src/aeat/diagnostics/test_profile.py`

## Verification

`uv run --no-sync pytest src/aeat/diagnostics/test_profile.py -q`
→ 9 passed.

Commit: `f71428dd0`.
