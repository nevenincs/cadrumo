---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f2627fa9c8dcad00ac88ae34c13da0cf0ef5e4b4219e61daf9a1c848218bfa95'
step_id: 'S26'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore wipeable key material across the current custody surface so recovery and password unwrap return zeroise-reachable buffers, noting the primitive is reachable today only through the forwarding port and must land after the surviving session package is renamed

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Establish which halves of the row are already satisfied before writing
  anything, by meaning rather than by symbol.
- Return a mutable buffer from both data-encryption-key unwraps, so the material
  the caller holds can be overwritten in place.
- State the irreducible limit in the docstrings rather than claiming a stronger
  guarantee than the primitives permit.
- Prove reachability by reading the buffer after the wipe, and bite-prove by
  reverting each unwrap.

## Outcome

The row's recovery half was already satisfied and nothing was added to it. A
recovery-material suite of ten tests already asserted mutability and then read
each buffer after zeroing, and already carried its own anti-tautology arm. That
is the correct outcome rather than a shortfall: the alternative was authoring a
second implementation beside a working one, which is what grounding by meaning
before writing exists to prevent.

What was genuinely missing is both data-encryption-key unwraps, each of which
yields the live bucket key and each of which returned immutable material. Both
now return a mutable buffer.

The finding inside the fix is worth more than the fix. One caller already wrote
`bytearray(unwrap_profile_session_dek(...))` -- copying the result into a mutable
buffer in order to wipe it, which left the original immutable object resident
and permanently unreachable. **The defensive copy created the very object it
could not clean.** No symbol search would have surfaced that site, because the
code reads as already correct; it is only wrong in a way visible from the type
it was defending against. Returning the buffer directly removes the copy rather
than adding one, so the fix makes the call site simpler and safer at once.

The limit is stated rather than papered over, and both docstrings now carry it.
The AEAD primitive returns plaintext as immutable bytes and nothing above it can
reach inside that object, so exactly one transient copy is irreducible at this
boundary. What the caller receives is wipeable; the library's own copy is a floor
this layer cannot raise. Claiming the key is fully wiped would have been the
over-claim this campaign exists to catch.

Proof is non-vacuous in both directions, which the row needed because each
obvious proof fails one way. Asserting the returned value is accepted is
satisfied by material that was never immutable; asserting a wipe call succeeded
is satisfied by immutable material, because there the refusal is what fires. So
each test reads the buffer AFTER the wipe and asserts the contents changed,
which passes only if the material was genuinely reachable and genuinely
overwritten. Reverting either unwrap reds exactly those two tests while leaving
the refusal arm passing.

The custody and master-key suites run 351 passed. The single failure is the
Spanish-default-render test, attributed elsewhere and separately rowed.

## Notes

The row's premise that the wipe primitive is reachable only through the
forwarding port was stale by the time the step ran: the primitive had been
relocated into custody hours earlier, so custody calls it directly as a sibling.

Adjacent surface was deliberately left alone and is now its own row. The master
key and the derived key-encryption key are the same class of gap across six
provider implementations and the derivation helper, and were not widened into
unasked. The argument for leaving them is real rather than procedural -- each
provider carries its own lifetime, and mutable master-key material changes what
every consumer holds, which is a wider blast radius than these two unwraps had.
That deserves a recorded decision in either direction rather than an assumption,
and the empirical test is whether any of the six callers already performs the
same defensive copy found here: such a copy is evidence that a consumer already
wants wipeable material and cannot get it.
