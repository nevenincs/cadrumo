---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:b9a28045e2c0ab996d50ca47375c07a483b038d6d72f177b88e5e2012612b337'
step_id: 'S123'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Extend the custody digest base with the digest field validator, the mismatch check and the canonical payload, then subclass the five records that hand-roll them

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/custody/digest_model.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule_records.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/recovery_artifact.py`
- `verify:` digest equality across all five records, before vs after -> `identical`
- `verify:` `pytest src/cadrumo/adapters/persistence/storage/custody -n 0` -> `pass` (238)

## Notes

The base now owns the mismatch refusal as well as the computation, keyed by a
message ClassVar. Each record keeps its OWN digest-shape field validator,
because those genuinely differ: one accepts a bare sha256, two accept the
`sha256:`-prefixed form, and a third spells the length-and-prefix check inline.
A triage sweep had described all five as identical "modulo the max-bytes
constant and error-message string", which is true of the computation and not of
the validation.

The digest is order-independent -- `bounded_canonical_json_bytes` sorts keys --
so adding a second base could not shift it through field reordering. That was
checked before the rebase rather than assumed, because multiple inheritance
would otherwise have been the obvious way to change a stored digest silently.

Proof is empirical, not argued: a fixed synthetic instance of each of the five
records was digested before the change and after, and the five hashes are
identical character for character. The inherited refusal was then
mutation-proved on a real record -- a valid marker accepts, the same marker with
a zeroed digest refuses with the inherited message.

Two records only are moved. The envelope, the recovery envelope and the capsule
commit still hand-roll the computation and are tracked separately: these verify
encrypted profile-password custody, and one proof per record is the price of
touching them.

Two subprocess reset tests fail when the whole custody suite runs and pass 3/3
in isolation -- an ordering or shared-state interaction, unrelated to a change
proved digest-neutral.
