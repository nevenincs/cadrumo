---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:32410fe37874f45b29a4651d337a72ba799d5363753d2878454a0c2090e5d329'
step_id: 'S42'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh close the drift between the curated operator help and the registered command tree, and gate the two surfaces against each other

## Scope

- `src/cadrumo/entrypoints/cli/`

## Description

- Establish by invocation, not by reading help text, whether the advertised
  first-run creation verb resolves.
- Restore the dropped registration, and gate every advertised command against
  the live command tree as a property.
- Sweep the surfaces the gates do not scan, and close the localisation gaps
  found in the same class.

## Outcome

Ruled a regression, established by invocation: before the change the verb
reported no such command; after restoring one registration block it lists and
renders its full help. The commit that dropped it never mentioned retiring an
operator verb and swept nothing -- the runtime bootstrap allowlist, the risk
table, the operator action catalogue, the terminal status screen, two
next-action builders, three agent-harness documents and a dispatch docstring all
still declared it. A verb the whole system described and none of it registered.

The gate that would have caught this ALREADY EXISTED and never ran: it is
integration-marked, and the default marker filter deselects it, so it printed
nothing ran. The drift shipped because the lane is unwatched, which is now its
own row. The replacement gate walks the typed help documents so the denominator
is structural, and covers the bare-root landing report the old gate could not
see -- which is exactly where the first-run citation lives. Registration is the
asserted property, deliberately not runnability, because curated help
legitimately advertises browsable groups.

A scope narrowing must be recorded beside what it excludes. Five further
advertised verbs -- profile delete, duplicate, rename, bundle export and the
subject-access-request surface -- have no implementation anywhere, and their
help rows were removed so the help stops misrouting operators. That makes the
help honest and simultaneously deletes the last user-facing description of
capabilities the product has silently lost, one of which is a data-protection
compliance surface. Seventeen command subtrees are unresolved in total. Restoring
them is a separate row and is NOT what this step delivered.

The localisation finding was the same class in another register. The reported
count was twenty-six; the measured count is three keys missing from all four
catalogues. They reach the translation call through a lookup table rather than as
a literal argument, so the scaffold's extractor cannot see them, they can never
be scaffolded, and they silently fell back to English -- a Spanish operator met
an English fragment in front of an otherwise Spanish refusal. Fixed through the
catalogue CLI with Spanish as source and real values in all four locales.

Verified independently: the localisation coverage gate passes.

## Notes

The restored registration restores only the INTERACTIVE door. The scripted arm
is refused by explicit design elsewhere, so scripted creation still returns a
refusal. That is a deeper design ruling and is carried as its own row rather
than reversed here.

Both commits were built through an isolated index because the help module and
all four catalogues carried peers' uncommitted work, and each blob was rebuilt
from HEAD plus only this step's hunks. The lesson already recorded in this
campaign was hit again and handled: an isolated-index commit leaves the shared
index stale against the new HEAD, so the same changes appear staged as a
reversal and a new file as a staged deletion. Those entries were repaired
deliberately after confirming they held no peer content.
