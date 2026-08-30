---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:98d397fe879ac5c0c7a82350196df9a689dc3a3092a5ed8f0406ae29bce46288'
step_id: 'S124'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Move the remaining three custody records onto the digest base, each with its digest proved unchanged, the envelope and recovery envelope and capsule commit still hand-rolling the computation

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/custody/records.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/recovery.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule_records.py`
- `verify:` digest equality across seven records, before vs after -> `identical`
- `verify:` `pytest src/cadrumo/adapters/persistence/storage/custody -n 0` -> `pass` (238)

## Notes

All five self-verifying custody records now inherit the computation, the payload
exclusion, the canonical bytes and the mismatch refusal, keeping only their own
digest-SHAPE validator, which genuinely differs between them. Hand-rolled digest
methods across the package fall from eighteen to three.

The three that remain are both correctly out of scope, and were checked rather
than assumed. `ProfileCustodyCapsuleLabel` chains two digests -- a content digest
and then a self digest over a payload INCLUDING it -- which is a wider shape the
base does not cover. `ProfileCustodySentinelRecord` has no ``self_digest`` field
at all; it only serialises canonically, so the base has nothing to give it.

The proof set was widened to seven: the five records plus two controls, the
chained-digest label and an already-migrated label head. All seven hashes are
identical before and after, so the change is neutral for the records it moved
AND for the ones it deliberately left.

The refusal is proved by a test that already existed: the records parser test
swaps a stored digest for ``sha256:ff...`` and asserts the parse is refused. It
passes against the inherited check.

The two subprocess reset tests that failed alongside the previous Step now pass,
which confirms that was ordering rather than the rebase.
