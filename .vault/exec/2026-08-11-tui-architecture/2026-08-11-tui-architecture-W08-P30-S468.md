---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:64579e831a1cb8aa1cf69bcd8cc5e89970c377a90533762d68fbe0f633236b0b'
step_id: 'S468'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Point the discriminating parse-envelope case at a command that exists and guard the fixture against the same drift, since it invoked a config profile preflight this CLI has never had so click resolved only the group and the case had silently become a second copy of the unknown-command test beside it

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_parse_error_envelope_names_its_command.py`

## Changes

`test_an_unknown_option_names_the_command_it_was_given_to` passes. 28 tests
across the parse/error suites pass with no regression.

THE FEATURE WAS NEVER BROKEN. Measured against the live registry:

    config profile status --bogus    -> command: "config.profile.status"
    app ledger preflight --bogus     -> command: "app.ledger.preflight"
    config profile preflight --bogus -> command: "config.profile"

The third is CORRECT. `COMMAND_SPECS` has no `config_profile_preflight` -- the
only `preflight` in this CLI is `app_ledger_preflight` -- so click resolves the
`config profile` group, refuses `preflight` as an unknown command, and names
the deepest thing it actually resolved.

THE CASE HAD STOPPED DISCRIMINATING. Its docstring calls it "a real command
with one wrong flag", and the module docstring contrasts it against
`aeat frobnicate`, which "resolves nothing". By naming a command that does not
exist, the case had quietly become a second copy of the unknown-command test
sitting directly beneath it -- which is what a stale fixture produces: not a
red test, a test of something else. It only turned red at all because it
asserted the deeper path.

Repointed at `config profile status --bogus`, which resolves.

THE GUARD IS THE PART THAT MATTERS. `_command_is_live` asks `COMMAND_SPECS`
whether the fixture's command exists, and both cases now state their premise:
the discriminating one asserts its command DOES resolve, the anti-tautology one
asserts `frobnicate` does NOT. A rename now fails here naming the fixture,
rather than silently changing what is measured.

Teeth: two defects, each restored by copy. Dropping the resolved-command read
in `_terminal_errors` fails the case (the feature is genuinely asserted), and
pointing the fixture back at `preflight` fails it too (the guard catches the
drift that hid this).

## Notes

I CHANGED A TEST AGAIN, and the same discipline applied as in S467: the live
`COMMAND_SPECS` registry was consulted before deciding which side was wrong.
The envelope reported exactly what it should for the input it was given; the
input was the defect.

Worth stating plainly because it cuts the other way from most of this campaign:
the last several firings found production defects behind failing gates, and it
would have been easy to keep assuming that pattern here and go looking for a
bug in the command resolution that does not exist.

REMAINING PRE-EXISTING FAILURES, unchanged and not from this step: the three
`test_audit` catalogue failures whose values come from the concurrent TUI/sync
commits, and the two gates blocked on operator decisions -- parity and the
`direction` shadow.
