---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e01f7a765fbe355ffb7a9fa2518cfb4a131fc4eedc8ae8b29ca08ee4e9337474'
step_id: 'S107'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh rule whether the master key and derived key encryption key should become wipeable like the two data encryption key unwraps now are, since six provider implementations and the derivation helper all return immutable material, or record why the master key is deliberately out of scope given each provider carries its own lifetime and a mutable buffer changes what every consumer holds

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/`

## Description

- Rule on extending the wipeable-buffer contract from the data-encryption-key
  unwraps to the master key and the key-encryption key derived from it.
- Run the empirical test rather than arguing from symmetry.
- Record the ruling as an enforced invariant rather than prose.

## Outcome

Ruled OUT OF SCOPE, and the reasoning is stronger than the question that
prompted it.

**The discriminator is ownership, not mutability.** An unwrapped data
encryption key is minted for one caller and handed over outright, so wiping it
is that caller's business and returning immutable material there was a genuine
defect. Master-key material is not owned that way: the unsecured provider
returns a module-level constant and hands the SAME object to every consumer,
verified rather than assumed. A mutable contract there would let one consumer's
wipe zero the key for every later caller, silently and unattributably.
Immutability is what makes returning a shared object safe, so the two surfaces
are not the same problem wearing different types.

That distinction also resolves something that looked like a second instance of
the defect found on the session-receipt path. The bucket session copies the
key-encryption key into a mutable buffer and zeroes it on close. That copy is
CORRECT, precisely because the session does not own what it was handed and must
not wipe the caller's object -- the same shape as the defective copy, opposite
verdict, and only the ownership question separates them.

The empirical test asked for was run and returned the opposite of the earlier
case: no consumer wipes a master key anywhere, so there is no evidence of a
holder wanting wipeable material and unable to get it. On the session data
encryption key the wanting was visible in the code, as a defensive copy that
defeated itself. Here there is nothing to find, which is what an out-of-scope
ruling needs in order to be a finding rather than an assumption.

## Notes

The ruling is recorded as an enforced invariant rather than as prose someone has
to remember, which is the right form for a decision whose failure mode is a
later agent reading the two DEK unwraps and generalising from symmetry.

Worth carrying into any future wipeability question: symmetry of TYPE is not
symmetry of CONTRACT. Two surfaces returning the same immutable type can want
opposite treatments, and the question that separates them is who owns the
object, not what it is made of.
