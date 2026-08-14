---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:b18d05d0056c60cf6bccf9e4c066e61d588135b254076fa4c572ae5230193150'
step_id: 'S64'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh open the core facade as the next import-cost lever

## Scope

- `src/cadrumo/core/__init__.py`

## Description

- Convert the eager import block to deferred module attributes without changing
  where any symbol lives.
- Delete the hand-written resolver chains that answered the same question a
  second way.
- Repair, rather than silence, the gate whose precondition the conversion
  removes.

## Outcome

The facade is now free to import: measured independently at 0.059 seconds against
a 0.057 second bare interpreter, from 0.372 seconds before. Three hundred and
forty-two names resolve through one deferred table, with set equality proven in
both directions and every name confirmed to resolve at runtime.

The honest framing of the result matters as much as the number, and the author
led with it rather than burying it. This is a NARROWER win than the storage
conversion. Consumers that genuinely need most of the facade pull those
submodules anyway, so the command-line entry point barely moves and the
supervised child gains about a tenth of a second — roughly a second across a
handover test, not the dominant term. A six-fold improvement on the facade
itself, with an explicit statement of who does not benefit, is worth more than
the headline alone.

Five hand-written resolver chains were deleted in the same change. They covered
twenty-five names through bespoke conditional ladders, answered a sentinel on no
match, and re-ran the import machinery on every attribute access rather than
caching. That was two mechanisms for one property, and it is why the eager
imports were invisible: the file already LOOKED lazy. One table now, and a
resolved name is written into module globals.

No import cycles were exposed here, checked rather than assumed: every
first-party module still imports, sixteen hundred and ninety-eight attempted with
zero failures. Unlike the storage conversion, this facade's evaluation order was
concealing nothing. No deferral was added to dodge anything.

## Notes

The conversion reddened a gate that records a real multi-hour outage, and the
repair is stronger than what it replaced. The old test asserted an ORDERING --
that the fallback resolver is defined after the first eager submodule import --
and its premise vanished when the last eager import did. The replacement asserts
that NO eager submodule import exists at all, which forbids the whole class
rather than policing a sequence within it: the outage required a module imported
during initialisation to reach back for a later-bound name, and that reach-back
needs an eager import to exist. The same assertion also fails the moment the
import-cost regression returns, so one statement guards both properties.

The live trigger was re-pointed one step later so it still fires a real settings
construction re-entering the facade from inside a submodule import, preserving
the hazard rather than the mechanics. And the late-bound name list stopped being
hand-written: three names were pinned when three were late-bound, all three
hundred and forty-two are now, so it reads the live map and refuses an empty one.

Flagging that rewrite for overrule rather than performing it quietly was the
right instinct on a module that documents an outage, and no new gate was written
because an existing one already discovers facades by traversal and picked this
one up unaided.

The key-derivation parameters are untouched, proven by an empty diff against
every file defining one.

One loose end from an earlier step in this campaign surfaced here and was
misattributed to a peer: the calibration setting shipped without its entry in the
environment example file, redding two configuration gates. It is this campaign's
own, and was routed back for repair.
