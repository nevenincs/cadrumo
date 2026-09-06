---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:21d6326403bc8a99c12deed290dfb27b865de40787b693e87a8e1d8b83dddd0e'
step_id: 'S481'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Follow a key factory into its caller, since a refusal that names its own reason writes the choice as a function whose every return is a key expression and the local rule declines a call by design, and correct the extras partition to require a delimiter so a prefix of a longer key is not read as evidence the key is written down

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 134 -> 132, and the full-literal residue is now ZERO. Every
remaining extra has no dotted literal written down anywhere in source.

BLIND SPOT 14. A refusal that must name its own reason writes the choice as a
FUNCTION, and the caller assigns the result before passing it on:

    def session_refusal_translation_key(refusal):
        return "cli...absent" if refusal in _LOGGED_OUT_REFUSALS else "cli...expired"
    ...
    key = session_refusal_translation_key(refusal)
    raise CliRefusedBoundaryError(translated_message=key, ...)

S464's local rule declines this deliberately -- its candidate value must be a
key EXPRESSION and a call is not one -- so both branches were invisible, with
the familiar asymmetry: whichever refusal a developer happens to trigger looks
translated.

A function qualifies only when EVERY return it makes is a key expression. One
return of anything else and none of its literals count, which is what keeps this
from becoming "any function that mentions a dotted string". S464's boundary is
untouched: a call to an arbitrary function still does not qualify a local.

A CORRECTION TO MY OWN MEASUREMENT. `cli.config.profile.manager_closed` was
counted as full-literal for eleven firings, and it is not written down anywhere.
It matched because my partition script asked `key in text`, and
`cli.config.profile.manager_closed_created` contains it as a PREFIX. The script
now requires a delimiter after the key. Two `cli.*` extras were similarly
inflated; the honest count is 132, not 134, and the no-trace group is 99 rather
than 98.

Teeth, two arms, each restored by copy: dropping the every-return requirement,
and removing the factory follow entirely. Both fail the gate.

## Notes

MY FIRST NEGATIVE ARM DID NOT BITE, the same way S471's did not. The
non-factory's result was passed to `navigate(...)`, so flow confirmation
rejected it and the every-return rule was never exercised -- the arm passed for
the wrong reason. It now passes the result to a translator, so the assertion
fails for the reason it names. A negative arm guarded by a DIFFERENT rule than
the one it is testing proves nothing about that rule.

WHAT THIS LEAVES. 132 extras, none carrying a literal: 123 `cli.*`, 5
`application.*`, 4 `tui.*`. Fourteen scanner blind spots have been closed across
S453-S481 and the residue no longer yields to source reading -- every remaining
key is invisible because nothing writes it, not because the scanner cannot see
it.

That is as far as evidence takes this. The `cli.*` and `application.*` groups
are answered by their live registries (S461, S463), which declare none of them;
the 4 `tui.*` have no comparable authority. The prune decision is the operator's
and is now the only thing standing between this gate and green.

STILL OPEN: the export-tree group stopped in S472 and characterised in S474, and
the two custody receipt cases that are environment-limited on this host (S479).
