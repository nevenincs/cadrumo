---
step_id: S273
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S253]]"
---

# cross-domain-continuity W09.P41.S273 + S244 — 7-file Category B storage migration

## Outcome

Commit `a69608c47`. Two source files changed; all 57 tests across both files
pass. Plan steps S273 (follow-up migration) and S244 (M202 must-fix) closed.

The other 5 of 7 Category B files listed in S273
(`test_command_suggestions`, `test_modelo_discovery_defects`,
`test_modelo_period_consistency`, `test_modelo_work_applicability_guard`,
`test_modelo_work_ux`) were already migrated in earlier sessions and
required no changes for S273.

## S244 must-fix — test_modelo_202_modality.py

- Replaced `_isolated_cli_backend` monkeypatch/unsecured fixture (10 env
  `setenv` calls + `EphemeralMasterKeyProvider`) with a single
  `isolated_profile_storage_root` autouse fixture.
- Fixed stale period token `"2026-1P"` → `"1P"` in the `work create`
  invocation. The CLI now expects bare registry period tokens with year
  passed separately via `--year`; the old composed form was never valid
  for the current CLI contract.
- All 10 tests pass.

## test_audit_remediation.py — profile-create isolation fix

The file had already been migrated to `isolated_runtime_profile` in a
prior session. However `test_overview_calendar_for_general_iva_includes_modelo_303`
was broken: `isolated_runtime_profile` pre-provisions a `test-runtime-profile`
bucket whose manifest has no profile record in the encrypted DB. When
`profile create` scans existing buckets for NIF uniqueness, it finds
this unreadable bucket and refuses with "Cannot verify tax-id uniqueness".

Root cause: cannot nest `isolated_profile_storage_root` inside
`isolated_runtime_profile` for the same test — `dispose_engine` in the
inner context shares state with the outer.

Fix: move the test into a `TestOverviewCalendarRequiresProfileCreate`
class that re-declares `_isolated_cli_state` as a class-level autouse
fixture backed by `isolated_profile_storage_root`. Pytest's fixture
resolution picks the class-level fixture over the module-level one,
giving the test a clean empty root without interfering with the other 3
tests in the module (which still use `isolated_runtime_profile`).

## Files changed

- `src/aeat/entrypoints/cli/test_modelo_202_modality.py` (S244: -17 lines net)
- `src/aeat/entrypoints/cli/test_audit_remediation.py` (-7 lines net; class extraction)
