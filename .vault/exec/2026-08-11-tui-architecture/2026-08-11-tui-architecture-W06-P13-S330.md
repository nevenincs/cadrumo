---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:3d6aeb4d968e217c2da294f88f4bddf0996d0747bd757f6100bcffe597e6ea54'
step_id: 'S330'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Convert the secret area's entry surface from a standalone application into a mountable screen, so a root shell can navigate to it: the credential entry is an application parameterised on an outcome type that RETURNS its result by exiting, and it carries its own worker-thread attempt lifecycle. Textual does not nest applications, so no root can mount it as it stands. Re-express it as a screen parameterised on the same outcome, dismissing rather than exiting, and rehost the worker machinery on the screen's host. Take this area FIRST of the three conversions because it is the cleanest -- one entry class with three subclasses and a single sub-step screen -- and because whatever pattern it establishes for the outcome-return and worker-rehost will be reused by the other two. Rehost every test that drives it through the application harness in the same change; a converted surface whose tests still construct an application proves the old shape, not the new one

## Scope

- `the secret area's credential entry surface`
- `its subclasses`
- `its recovery sub-step`
- `and every test that drives it`

## Changes

- `M` `src/cadrumo/entrypoints/tui/secret/credentials.py`
- `M` `src/cadrumo/entrypoints/tui/secret/login.py`
- `M` `src/cadrumo/entrypoints/tui/secret/passphrase.py`
- `M` `src/cadrumo/entrypoints/tui/secret/registration.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/surfaces.py`
- `M` `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_login_screen.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_login_screen_restored_profile.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_screen.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_recovery_words.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_language_switch.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_theme.py`
- `M` `dev/tui/_coverage.py`
- `M` `dev/tui/tests/test_tui_visual_inventory.py`
- `R` `CredentialApp -> CredentialScreen`
- `R` `LoginApp -> LoginScreen`
- `R` `PassphraseApp -> PassphraseScreen`
- `R` `RegistrationApp -> RegistrationScreen`
- `R` `run_credential_app -> run_credential_screen`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/secret src/cadrumo/entrypoints/tui/tests/test_login_screen.py src/cadrumo/entrypoints/tui/tests/test_login_screen_restored_profile.py src/cadrumo/entrypoints/tui/tests/test_registration_screen.py src/cadrumo/entrypoints/tui/tests/test_registration_recovery_words.py src/cadrumo/entrypoints/tui/tests/test_registration_language_switch.py -m integration -n0` -> `fail`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_theme.py dev/tui/tests/test_tui_visual_inventory.py src/cadrumo/entrypoints/tui/devtools -m unit -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`

## Notes

One assertion is left failing and is not caused by this Step:
`test_every_field_and_action_is_actually_on_screen_not_only_present[narrow]`
requires every control to sit inside an 80x24 terminal, and `btn-change`
renders at row 26 against a 22-row viewport. Reproducing the
pre-conversion application topology fails identically, so the screen
conversion moves it one row and does not cause it. Carried forward as its
own row rather than resolved by weakening the containment assertion or by
silently reshaping the interface.

Textual does not apply a `Screen` subclass's `CSS` attribute, only
`DEFAULT_CSS`, so the rename silently dropped every stylesheet while nearly
all assertions still passed; the surfaces carry `DEFAULT_CSS` with
`SCOPED_CSS` disabled, and the standalone host carries the base stylesheet.

The added screen layer widened existing races in the driving tests, which
now wait on the real postcondition rather than on a longer pause.

Production changes were carried to main inside `ccfddea81a`, an unrelated
operand-custody commit, before this Step could commit them; content verified
correct at HEAD.
