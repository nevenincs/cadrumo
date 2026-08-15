---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:a192bb7ce74d078fe37c12807cf23e76819fe6b5764fc064536d48cfeabc4146'
step_id: 'S19'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh dissolve the forwarding port package in five ordered parts

## Scope

- `src/cadrumo/application/profile_custody/ and src/cadrumo/application/user_profile/_custody_ports.py and src/cadrumo/domain/user_profile/_protocols.py and src/cadrumo/adapters/persistence/storage/ and src/cadrumo/adapters/outbound/aeat/ and src/cadrumo/application/ and src/cadrumo/entrypoints/cli/`

## Description

- Turn the string indirections into plain imports and delete the module-shaped
  protocols that photocopy an adapter facade, with the casts they existed to type.
- Relocate the record-shaped ports that genuinely narrow a collaborator, one
  symbol per atomic commit with its full consumer sweep.
- Replace every remaining direct provider consumer with per-profile custody and
  session material.

## Outcome

All five parts landed. The dynamic string indirection is gone entirely -- from
forty-nine call sites to zero -- the module-shaped protocols and the casts that
typed them are deleted, seven record-shaped ports were relocated one atomic
commit each, and the last four direct provider consumers are removed. Measured
independently: **zero** non-test references to the provider family across the
application layer, the entry points, the domain, the core and the outbound
adapters. The family survives only inside the persistence adapter that defines
it.

Two findings from part five are worth more than the removal itself.

**The fallback that was removed was already broken wherever it was reached.** A
capsule-published bucket has no shared-master manifest, so entering the provider
against one raises a storage error -- and neither reader caught it, both guarding
only the not-found refusal. A function documented to degrade was propagating a
storage error instead. Confirmed by reconstructing the deleted branch against a
freshly published capsule rather than inferred from the code.

**The repair path is where a keyless probe would have destroyed data.** Those
probes call a row unreadable when it will not decrypt, and the quarantine action
MOVES exactly those rows -- so a keyless run would have reported a sound bucket
as entirely corrupt and archived all of it. The substrate was probed BEFORE the
change and already fails closed before any row is read, so removing the provider
closed a throwing detour rather than opening a hole. That reasoning is now
written into the context manager so nobody re-adds a fallback to make the probe
"work".

Both close conditions are met. The integration lane over the custody scope is 62
passed, exit zero, against a scope of 1015 tests. The serial pass matched nothing
in scope and SAID so rather than reporting a false green.

## Notes

**The cross-package private reach did NOT shrink, and that is reported as a
finding rather than improved away.** Seven names remain, because all thirty-eight
delegates are still present: part five removed the PROVIDER consumers, while the
delegates forward the surviving SESSION substrate, a different surface never in
this step's scope. Those delegates carry the annotations, and the annotations are
what the seven names are for. The reach reaches zero as a consequence of whatever
removes the delegates, one step later than the original framing assumed. No
private symbols were promoted to make the number look better.

The arithmetic is stated plainly in the report: a two-name site was inherited and
a seven-name site handed back; the SITE is inherited and still unbaselined, the
widening is owed.

Two tests asserted the removed contract BY NAME -- that repair opens a session
for bootstrap-exempt work. They now assert what must hold instead: preview
reports nothing, the mutating verb refuses, and the row is still live and still
decrypts afterwards, each pairing a sessionless read with a served one so an
empty result is provably the missing key rather than a missing row.

One rename exposed a fixture keyed by TEST NAME: an always-on database binding
exempted one hardcoded node, so renaming that test silently re-armed the override
and broke the runtime inside its own setup, far from the cause. It is a requested
fixture now, so the framework checks it and a rename cannot quietly break it.

The absence gate is red at close, on an UNDECLARED reach in an uncommitted edit
to the operator authority module -- a NEW reach into the shared-master package
appearing in the same window that the last one was removed. It is not this step's
and was deliberately not declared on the author's behalf, because a declaration
must name where the reach is going and only its author knows that. Routed to its
owner.
