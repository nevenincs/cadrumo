---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:debe25e08b05b4fae970dd82c715cc07aa4b120e770c248b6fb53bd0b44a0d65'
step_id: 'S341'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Collapse the two screen-host applications into one, a duplication declared rather than hidden by the agent that created it: the profile conversion introduced a generic screen host in the shared components package, depending only on the interface toolkit and the local theme, and the secret area's earlier credential host is now a duplicate of it. Both exist to carry a single screen for a standalone, non-navigated run. They were left separate deliberately because the secret modules were being edited concurrently and a cross-area rename would have collided -- that was the right call at the time and is not a reason to keep two. Retire the area-specific host in favour of the generic one, update every consumer, and confirm the standalone runs of both areas still start; a second host is exactly the parallel implementation the architecture rules forbid, and it will drift the moment one area needs a host behaviour the other does not

## Scope

- `the shared components screen host`
- `the secret area's credential host`
- `and every standalone runner and test that constructs either`

## Changes

- `D` `CredentialHostApp` (`src/cadrumo/entrypoints/tui/secret/credentials.py`)
- `M` `src/cadrumo/entrypoints/tui/secret/credentials.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/surfaces.py`
- `M` `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_login_screen.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_login_screen_restored_profile.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_screen.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_recovery_words.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_language_switch.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py`
- `verify:` `uv run --no-sync pytest --collect-only -q src/cadrumo/entrypoints/tui` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/secret <the login and registration suites> -m integration -n0` -> `fail`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`

## Notes

Every consumer imports the surviving host from its canonical defining module
in the shared components package, not through the secret area's module. A
re-export there would have been the cheaper sweep and is the construct the
architecture rules forbid; none remains.

Two assertions fail only under load and are not caused by this Step. Both sit
on the recovery-handoff confirmation, both pass in isolation across repeated
runs, and the failing parametrisation differs between runs, which is the
signature of a race rather than a defect. Removing this Step's only
behavioural addition to the standalone run -- the host installing the theme,
which each screen already does for itself -- does not change the outcome, so
the addition is not implicated. The handoff waits on a bounded thread event
while a real key derivation runs, and the machine carries several concurrent
suites, so the bound is the suspect. Carried forward rather than silenced by
lengthening a sleep.

Files were carried to main inside `00de767e9a`, an unrelated commit by
another author, before this Step could commit them; the retirement, the
canonical imports and the absence of a re-export were verified at HEAD.
