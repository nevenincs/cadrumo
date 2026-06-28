---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S230
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W02.P11.S230

## Outcome

Fixed M303 SII monthly cadence: `work create --period 01` was accepted by the
CLI period parser (which composed `2025-01`) but `bindings list --period 01`
raised a `RegistrySnapshotError` because `select_revision` rejected `"01"` as
not in `period_selector.periods = ["1T", "2T", "3T", "4T"]`.

**Root cause**: the `2023-y-siguientes` revision only declared quarterly periods.
Under Art. 62.6 RD 1624/1992 (modified by Orden HFP/187/2017), SII-enrolled
taxpayers must file M303 monthly. The registry had no monthly period entry for
this revision.

**Changes to `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`:**

- `period_selector.periods`: added `"01"` through `"12"` alongside quarterly tokens
- Added `[[revisions.2023-y-siguientes.filing_schedules.profile_conditions]]` to
  the quarterly `modelo-303-trimestral` schedule: `iva.sii_enrolled not_equals true`
  to exclude SII-enrolled taxpayers from the quarterly path
- Added new `[[revisions.2023-y-siguientes.filing_schedules]]` `modelo-303-mensual-sii`
  with `iva.sii_enrolled equals true` profile condition and `periods = ["01"..."12"]`
- Added representative monthly deadline windows for 2025 and 2026 (January,
  June, December/January anchors) with `closes_on = last day of following month`
  per Art. 71 RD 1624/1992
- Registered both filing schedules and monthly windows in the construct manifest

**Tests added to `test_modelo_303_registry.py`:**
- `test_modelo_303_sii_monthly_snapshot_resolves_for_each_period`: builds snapshot
  for periods 01, 06, 12 and asserts revision resolves to `2023-y-siguientes`
- `test_modelo_303_sii_monthly_filing_schedule_matches_sii_enrolled_profiles`:
  uses `applicable_filing_schedules` to verify SII profile → monthly schedule,
  standard profile → quarterly schedule, and neither gets the wrong one

**Test updated in `test_engine.py`:**
- `test_modelo_303_quarterly_windows_resolve`: filtered `period_kind == "quarterly"`
  since monthly windows now also appear in `deadline_windows(year)` for 2025/2026;
  added assertion that monthly windows are also present

118 tests across all four affected test modules pass. Ruff clean, pyright 0 errors.

## Commit

`2dbe9d6e8` — S230: M303 SII monthly cadence — add monthly period selector + filing schedule
