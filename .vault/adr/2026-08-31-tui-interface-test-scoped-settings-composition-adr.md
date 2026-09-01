---
tags:
  - '#adr'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:98c5ba648ed9c789e26706886e51fd151c3acaf4095c63356182191250b93096'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - '[[2026-08-31-tui-interface-settings-override-composition-probes-reference]]'
---

# `tui-interface` adr: `test-scoped settings composition` | (**status:** `proposed`)

## Problem Statement

An active settings override silently pins every field the caller did not
override, so a later environment change inside the block cannot be seen. The
observed failure is two locale tests in the flow TUI suite asserting English
copy inside an output-language scope and receiving Spanish. The cause is not in
those tests and not in the scope: a session-scoped autouse fixture overrides an
unrelated key-derivation flag for the entire run, and that unrelated override is
what pins the language.

The general statement, which is what makes this a contract rather than a bug: an
override block is a FROZEN SNAPSHOT, and nothing rebuilds it. Any mechanism that
works by changing the environment and dropping the settings cache is therefore
inert for the whole duration of any override, whatever field that override was
about. The failure is silent -- the reader gets a plausible value, not an error.

## Considerations

Three facts were established by experiment rather than by reading alone, and one
of them removes the most attractive fix.

1. With no override active, setting the environment variable and dropping the
   cache resolves to `en`. Inside an unrelated override it resolves to `es`.
   The scope is not inert; the override is opaque to it.
2. The language is NOT wrongly marked explicit. `override_settings` already
   restores `model_fields_set` to the union of what the source had explicitly
   set plus the override keys, so `cadrumo_output_language` correctly reports
   as unset inside the block. The resolver falls through to the settings value
   and finds the SNAPSHOTTED one.
3. Therefore the pin is the VALUE, not the explicitness -- and the fix that
   suggests itself from reading `merged = current.model_dump()` does not work.
   Carrying only explicitly-set fields forward and letting the rest re-derive
   was implemented and measured: still `es`. The merged dict is not the
   problem, because the object is built ONCE at block entry and every later
   read returns that same object.

This matters because the existing root-derived-storage remedy has the shape of
an answer and is not one. That remedy drops derived fields from the merged dict
so they re-derive under a new root, and it is guarded on the PARENT setting
being overridden. Language has no parent setting: it derives from the
environment. Adding it to that taxonomy would change nothing, because the guard
would never fire for the case that breaks.

## Considered options

**A. Rebuild the active override when the settings cache is reset.** Dropping
the cache would re-derive the pinned override's unset fields from the current
environment, keeping its explicit overrides. DEMONSTRATED WORKING: inside an
unrelated override, setting the environment and rebuilding resolves `en`; the
unrelated override still applies; removing the environment variable and
rebuilding returns to `es`, so it tracks the environment in both directions
rather than latching once. Cost: it gives cache reset a meaning it does not have
today -- reset currently discards a memo, and would begin to mutate live
override state.

**B. Take language out of the settings-derived path entirely,** so it is read
from one place no override can pin. This is the one-mechanism resolution and the
cleaner end state, and it makes the whole class impossible rather than fixing
one member. Cost: it moves a PRODUCTION read path, not a test-only one, and the
resolver today deliberately composes three sources in priority order -- explicit
setting, active profile, default.

**C. Merge only explicitly-set fields into the override.** REFUTED BY
EXPERIMENT, recorded so it is not retried: it is the fix that follows from
reading the flattening, and it leaves the observed behaviour unchanged because
the snapshot is still built once at entry.

## Constraints

The stimulus under test cannot itself use an override. The language switch these
tests exercise happens inside a Textual message-pump callback, where the
contextvar token cannot be reset, so the mid-block switch must remain reachable
by some mechanism other than opening a nested override. This is what rules out
"make the scope nest an override": it was tried, made the first assertion pass
and broke the second, and was reverted.

Whichever option lands must keep an override's OWN fields authoritative. A
rebuild that re-derived the overridden key would defeat the primitive.

## Implementation

Option A is the narrow one and its blast radius is smaller than first assumed:
the rebuild can live entirely inside the cache reset, because the override is
held in a context variable that the reset can read and replace. It does not
require touching each override site. Resetting the block's own token still
restores correctly, since a context variable token restores the value that was
current when that token was created, discarding intermediate sets.

Option A is proposed as the immediate remedy and option B as the end state they
converge on: A makes the existing mechanism compose, B removes the second
mechanism so composition is not required. Landing A first is reversible and
leaves B open; landing B first is a production change made under test pressure.

## Rationale

The row this comes from states the question exactly: it is not which mechanism
wins, it is why there are two. Both other framings -- cross-test leakage, and an
inert scope -- were tested and refuted, so the remaining explanation is
structural. An override that freezes fields it was never asked about is a
primitive whose blast radius is invisible at the call site: the fixture pinning
the language mentions only a key-derivation flag.

## Consequences

Any test that changes the environment expecting a settings read to follow is
currently unreliable whenever an override is open, and the session-scoped autouse
fixture means one is open for the entire run. So the reliability question is not
limited to language; language is where it happened to surface. Under option A
that class closes. Under option B it closes only for language, and the next
environment-derived field to be read inside an override reopens it.

The cost of option A is that cache reset becomes a state mutation, which must be
said plainly wherever it is documented, or the next reader will assume reset is
free.
