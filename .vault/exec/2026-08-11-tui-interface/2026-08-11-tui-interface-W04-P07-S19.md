---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5c76989e611880e449ebf1e6377cc89bf09efe8d3758a9997add6e23f3a003a6'
step_id: 'S19'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Complete profile-secret creation and registration presentation through public application contracts

## Scope

- `src/cadrumo/entrypoints/tui/secret/registration.py`

## Changes

- `R` `src/cadrumo/entrypoints/tui/secret/app.py` -> `src/cadrumo/entrypoints/tui/secret/registration.py`
- `M` `src/cadrumo/entrypoints/tui/components/widgets.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/fixture.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/surfaces.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_login_screen.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_login_screen_restored_profile.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_language_switch.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_recovery_words.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_screen.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_theme.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_visual_verification.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/ --collect-only -q` -> `pass` (0 errors)

## Notes

Two real defects found and fixed while sweeping consumers, both from earlier W02/W03 work, not this relocation: `SourceActionCard` inherited Textual `Vertical`'s default `height: 1fr` uncorrected, so a second card on the same screen split available space instead of sizing to content (fixed with an explicit `height: auto` override); and `test_visual_verification.py`'s manager fixtures never injected `ProfileManagerApp.launch_source`, leaving its source-action buttons permanently disabled and unfocusable (fixed by injecting a real no-op callable).
