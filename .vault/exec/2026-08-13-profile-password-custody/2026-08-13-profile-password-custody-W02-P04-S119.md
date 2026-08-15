---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:ce4b7b1076598c0c602502e58763ac3c8ee8407b30326cc4bc701a090218f205'
step_id: 'S119'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh widen the resume return type to match the wipeable material it now yields, since the unwrap was changed to return a mutable buffer while the enclosing signature still promises immutable bytes, so every caller is typed to receive material it cannot wipe and the call sites lose the property the change existed to give them

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_acceleration_receipt.py`

## Description

- Confirm the widening itself had already landed on this branch: the resume declares
  the resumed key as a mutable buffer, the application hop that carries it declares the
  same, and the login path wipes the buffer the resume returned instead of a copy.
- Enumerate every caller of the resume path and confirm the chain type-checks end to
  end under all three of the project's type checkers.
- Add the missing behavioural proof at the resume boundary: mint a receipt through the
  production path, resume it, assert the runtime object is a mutable buffer holding the
  minted key, wipe it, and read it back zeroed.
- Prove the new guard bites by yielding immutable bytes from the resume at runtime,
  patched from outside the repository, with the declared annotation left intact.

## Outcome

The row is about a security property, not an annotation. The unwrap yields a wipeable
buffer so a caller can zeroise the live bucket key; while the enclosing signature
promised immutable bytes, every caller was typed to receive material it could not wipe,
and the login path did the only reasonable thing for that contract - it copied into a
buffer and zeroised the copy, leaving the real key resident and unreachable. The wipe
looked successful, which is why no behavioural test noticed.

The declaration and the caller correction were already on the branch when this row was
picked up. The caller that now genuinely wipes is the single resume authority in the
user-profile login module: it hands the session its own copy and zeroises the buffer the
resume returned, in a finally block, rather than a copy of it.

The caller census is three hops and no more. The custody package's own resume function
is the origin; the profile-custody application facade re-declares the same buffer type
on the way through; the user-profile login module's private acceleration-receipt resume
declares it a third time and is where the wipe happens. The custody package facade
re-exports the name lazily and does not restate the type. Every other reference is a
test. All three hops declare the mutable buffer, and the full type-check run reports no
diagnostic on any file in that chain.

What was missing was the proof. The existing guard read the declared return annotation
and asserted the buffer type appeared in it - which is a restatement of the declaration,
not a test of the property. A resume that annotated the buffer while yielding immutable
bytes would satisfy it and leave the defect fully intact.

The added case takes the value the production mint and resume pair actually hands back,
proves it holds the minted key, wipes it, and reads it again zeroed. Nothing is
substituted: a real receipt is minted through the production path, its session key is
custodied in the real OS credential store, and the resume unwraps it under that key,
which is why the case carries the credential-store marker rather than sitting in the
default lane. The annotation-reading sibling is kept, because it is the only arm that
can run on a host with no credential store.

The bite proof is the discriminating one. Narrowing the resume to yield immutable bytes
at runtime while preserving its declared annotation - patched from outside the
repository, so no tracked file changed - leaves the annotation-reading guard green and
reds only the new behavioural arm. That is the exact gap the row asked to close.

No cryptographic behaviour changed. The buffer is the same material the AEAD primitive
recovers; only the proof that a caller can reach and overwrite it is new.

## Notes

- The custody test directory is not enrolled in the project's credential-store lane
  recipe, which names the master-key, storage, user-profile, CLI session and secure-SQL
  directories but not this one. The new case and the pre-existing acceleration class in
  the sibling roundtrip module therefore do not execute under that recipe. This is not a
  regression introduced here, but it bounds the guard's reach until the recipe enrols
  the directory; raised for routing rather than edited, since the recipe is outside this
  row's ownership.
- The credential-store lane is flaky on this host independently of this change: the
  untouched roundtrip module fails on its own with a different case each run, always as
  a credential that was written and round-trip verified at mint but read back absent.
  The new case passed eight of eight runs alone and six of six paired, with one failure
  in eleven paired runs of the same family. Recorded rather than absorbed.
- The storage test package carries substantial ambient red from concurrent work -
  missing public exports from the master-key surface, schema-lineage floor drift, and
  sensitive-surface inventory drift. None of it touches this row's files.
