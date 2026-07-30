---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S34'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Refuse a live session when an active profile carries no fiscal identity, closing the certificate path where a cleared field disarmed both the credential guard and the deferred session comparison, gated by a sweep over the whole provider enum

## Scope

- `src/cadrumo/application/auth/_sessions.py`

## Description

- Establish by execution that a profile's fiscal identity can be cleared after
  creation, that the profile remains promoted afterwards, and that the
  certificate provider then reaches a live bind with neither guard refusing.
- Establish, also by execution, that a profile still in setup can be minted
  carrying no facts at all, which decides the refusal's shape.
- Carry the profile's lifecycle status onto the auth facts projection, since
  distinguishing an identity never recorded from one recorded and later removed
  needs the record and not just its values.
- Refuse at the point where the deferred comparison's expectation is chosen,
  inside the branch only a provider without an operator-configured credential
  reaches, leaving the existing credential-side refusal untouched.
- Exempt a profile still in setup, and leave the no-profile case to the
  refusals that already own it rather than answering it with a message about
  restoring a field.
- Add the operator-facing refusal in all four locales through the locale CLI.
- Gate the property across every provider rather than the one that was missed.

## Outcome

The path is closed at the auth layer for a promoted profile. The refusal is one
branch; the gate is a sweep over the provider enum, asserting that no provider
binds a session against a blank profile identity, so a provider added later
that reaches a different line is covered by a test that already exists.

Verification: the auth application suite passes at 221, and the credential
surfaces at the CLI boundary pass in both the unit and integration lanes, run
without workers so no serial test was held out. Lint, format and type check
clean.

The anti-tautology check behaved informatively rather than merely passing.
Neutering the refusal reddens the certificate arm of the sweep and leaves the
two Cl@ve arms green, because those are defended by the older credential-side
refusal. That is the correct reading: the sweep asserts a property that
several guards jointly uphold, and it names which provider depends on which.

## Notes

This closes one of two doors. The refusal covers a promoted profile whose
identity was removed, which is the state proven reachable. A profile still in
setup is deliberately allowed to authenticate, so the equivalent protection
for that case has to come from the guard on the read it performs, which is
owned elsewhere. Until that lands the window is narrower - it needs a profile
mid-setup rather than any profile - but it is not closed, and this record
should not be read as closing it.

The end-to-end path from a bound foreign session through to an adopted read is
strongly indicated and was not executed here. What is proven is that both
guards decline to refuse. The remaining link is being confirmed against an
existing reproduction harness rather than a second one built here.

One fact about this module rather than a general claim: the profile
registration command's documentation states that a profile minted at the start
of setup has its fiscal id reserved, and nothing enforces that - the early-mint
arm validates shape only and accepts zero facts. This is the third place in
this subsystem where documentation asserts a guarantee the code does not make,
after the credential guard's fail-closed description and the deferred check's
description of where the certificate is compared. All three were load-bearing
for a security property, and all three were believed before being tested.

This Step's commit carried two locale hunks not authored here, and the second
one matters. The locale edits were written several hours earlier, across an
interruption; the locale tool rewrites whole files; and a commit naming paths
publishes working-tree content. So the commit published a stale whole-file
snapshot that re-added a censal message key another campaign had deliberately
removed in the interim, and reflowed a second key's quoting without changing
its content.

The consequence was not mis-attribution but a false green. That removal had
left a message key referenced by code and absent from every catalogue, which
is precisely what the catalogue parity gate exists to catch. The accidental
re-add repaired that before the gate ran, so the catalogues are consistent
today for the wrong reason. Adjudicated as leave-as-is: the pending censal
change references both keys deliberately, for a never-recorded identity and a
removed one, so both become legitimate when it lands and removing either now
would break the gate. The end state is right; the route to it was not.

The guard lesson is the reusable part. The pre-commit check compared the set
of staged PATHS and was read as confirming the staged CONTENT. Those are
different questions, and a path-level check cannot see foreign content inside
a file legitimately owned - which makes it structurally insufficient, not
merely weak, for any generator that rewrites whole files from a working tree of
unknown age. It was found only by re-reading the commit's own diffstat well
after the fact, on noticing that a one-key change reported eight changed lines
per catalogue.
