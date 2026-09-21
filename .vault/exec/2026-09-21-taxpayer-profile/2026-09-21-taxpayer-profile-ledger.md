---
tags:
  - '#exec'
  - '#taxpayer-profile'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:a184c6b2c2b078feae6e7beb4b093103ed7fde76bb51ef34ba6223aac45a4869'
related:
  - "[[2026-09-21-taxpayer-profile-plan]]"
---

# `taxpayer-profile` ledger

## Changes

- `S01` `A` `.agents/session-briefs/handoffs/2026-09-21-taxpayer-profile-checkpoint.md`
- `S01` `A` `.vault/plan/2026-09-21-taxpayer-profile-plan.md`
- `S01` `A` `.vault/index/taxpayer-profile.index.md`
- `S01` `verify:` `targeted source-state and fact-trace audit` -> `pass`
- `S02` `M` `.agents/session-briefs/handoffs/2026-09-21-taxpayer-profile-checkpoint.md`
- `S02` `M` `.vault/plan/2026-09-21-taxpayer-profile-plan.md`
- `S02` `verify:` `focused-integration-selection` -> `pass`
- `S03` `M` `.agents/session-briefs/handoffs/2026-09-21-taxpayer-profile-checkpoint.md`
- `S03` `verify:` `production-profile-snapshot-caller-search` -> `pass`
- `S04` `M` `src/cadrumo/application/user_profile/projections.py`
- `S04` `M` `src/cadrumo/application/user_profile/tests/test_effective_window_end_is_reported_not_enforced.py`
- `S04` `M` `.agents/session-briefs/handoffs/2026-09-21-taxpayer-profile-checkpoint.md`
- `S04` `verify:` `ty-check` -> `pass`
- `S05` `M` `.agents/session-briefs/handoffs/2026-09-21-taxpayer-profile-checkpoint.md`
- `S05` `verify:` `snapshot-event-binding-export-selection` -> `pass`
- `S06` `M` `src/cadrumo/application/user_profile/section_rows.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/config/_profile_repeatable_row.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/config/profile_command_specs.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/config_payloads.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/config/tests/test_profile_add_row_cli.py`
- `S06` `M` `src/cadrumo/locales/en/cli.yml`
- `S06` `M` `src/cadrumo/locales/es/cli.yml`
- `S06` `M` `src/cadrumo/locales/ca/cli.yml`
- `S06` `M` `src/cadrumo/locales/hu/cli.yml`
- `S06` `M` `src/cadrumo/locales/en/application.yml`
- `S06` `M` `src/cadrumo/locales/es/application.yml`
- `S06` `M` `src/cadrumo/locales/ca/application.yml`
- `S06` `M` `src/cadrumo/locales/hu/application.yml`
- `S06` `verify:` `uv run --no-sync ty check targeted-profile-row-files` -> `pass`
- `S07` `M` `src/cadrumo/application/user_profile/fact_write.py`
- `S07` `M` `src/cadrumo/application/user_profile/overview.py`
- `S07` `M` `src/cadrumo/application/user_profile/section_rows.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/account.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/installed_session.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/tests/test_account.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/tests/test_manager_screen.py`
- `S07` `A` `src/cadrumo/entrypoints/tui/profile/tests/test_repeatable_row_race_safety.py`
- `S07` `verify:` `targeted ruff and ty` -> `pass`
- `S08` `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `S08` `M` `src/cadrumo/locales/en/flows.yml`
- `S08` `M` `src/cadrumo/locales/es/flows.yml`
- `S08` `M` `src/cadrumo/locales/ca/flows.yml`
- `S08` `M` `src/cadrumo/locales/hu/flows.yml`
- `S08` `verify:` `profile application flows and tui locale domains complete` -> `pass`
- `S07` `M` `src/cadrumo/entrypoints/tui/profile/tests/test_repeatable_row_race_safety.py`
- `S08` `verify:` `TUI copy keys resolve in four locales` -> `pass`
- `S09` `A` `dev/acceptance/profile/__init__.py`
- `S09` `A` `dev/acceptance/profile/scenario.py`
- `S09` `A` `dev/acceptance/profile/cli_journey.py`
- `S09` `A` `dev/acceptance/profile/installed_tui_child.py`
- `S09` `A` `dev/acceptance/profile/tui_journey.py`
- `S09` `A` `dev/acceptance/profile/tests/__init__.py`
- `S09` `A` `dev/acceptance/profile/tests/test_scenario.py`
- `S09` `A` `dev/acceptance/profile/tests/test_cli_journey.py`
- `S09` `A` `dev/acceptance/profile/tests/test_tui_journey.py`
- `S09` `verify:` `acceptance harness ruff format and ty` -> `pass`
- `S10` `M` `dev/acceptance/profile/cli_journey.py`
- `S10` `M` `dev/acceptance/profile/installed_tui_child.py`
- `S10` `M` `dev/acceptance/profile/tests/test_cli_journey.py`
- `S10` `M` `.agents/session-briefs/handoffs/2026-09-21-taxpayer-profile-checkpoint.md`
- `S10` `verify:` `targeted-ruff-format-ty` -> `pass`
- `S10` `M` `dev/acceptance/profile/tui_journey.py`
- `S10` `M` `dev/acceptance/profile/tests/test_tui_journey.py`
- `S10` `M` `.vault/audit/2026-09-21-taxpayer-profile-audit.md`
- `S10` `A` `dev/acceptance/profile/tests/test_installed_tui_child.py`
- `S10` `verify:` `acceptance-harness-14-tests` -> `pass`

## Notes

- `S01` Mandatory Luna Max route failed to return twice; vaultspec-rag service unavailable because its interpreter lacks a supported accelerator. Continued from retained preflight evidence and targeted reads under session-policy 1.7.
- `S02` The failing probe reproduced the intended defect; missing in-flight-write plus F5 integration remains assigned to P03.S07. Temporary failing regression was removed and will land atomically with the projection fix.
- `S03` PR6 implementation blocked pending a cross-lane temporal-context decision; three bounded options recorded.
- `S05` Verification-only Step; no persistence namespace or Modelo source edit was required. Production filing snapshot pinning remains blocked.
- `S07` Installed-generation aggregate currently fails before profile composition because concurrent calendar fixture omits required OverviewCalendar.evaluated_on.
- `S08` Repository-wide locale status remains open for 48 concurrent assets/modelo CLI cells and 8 unrelated inventory declarations.
- `S07` Reopened after high review: fixed same-profile stale result and typed add/remove coverage.
- `S08` Removed final CLI-owned key from TUI profile manager.
- `S09` Installed wheel execution intentionally remains S10.
- `S10` canonical import gate unavailable: governed tree changed concurrently; no PROFILE-01 occurrence
- `S10` canonical import gate stable but failed on 10 external findings; no PROFILE-01 occurrence

