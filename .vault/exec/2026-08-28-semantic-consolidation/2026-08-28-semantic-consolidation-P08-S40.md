---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:51a0a20ed844f11d6ef7ee51d93a648c4029f074174a1647184d7b26188cee38'
step_id: 'S40'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Migrate the secure-object revision id from its delimiter-joined hash convention to the canonical content-hash primitive

## Scope

- `src/cadrumo/adapters/persistence/storage/sql/_secure_object_crypto.py`

## Changes

- `A` `src/cadrumo/adapters/persistence/storage/sql/tests/test_revision_id_join_is_unambiguous.py`
- `verify:` `pytest -n 0 -m ""` -> 2 passed
- `verify:` all 77 declared secure-object namespaces match `[a-z0-9._-]+`; none carries the join delimiter
- `verify:` no literal `namespace=` argument anywhere in `src/cadrumo` falls outside that grammar

## Notes

The step asks to move `derive_revision_id` from its ``-joined hash onto
`content_hash_hex`. The migration was NOT performed, and the reason is a
measurement rather than a reluctance.

### The stated remedy is a persisted-format decision

`revision_id` is a stored `VARCHAR_64` column, and
`verify_revision_self_consistency` recomputes it from the lineage columns at
read time as a tamper gate. Changing the derivation restamps every stored row
and fails that gate on every row not yet migrated. The module's own docstring
already adjudicated this: bringing anything new under the digest "would restamp
every stored `revision_id`, which is a persisted-format decision rather than a
local fix."

A mechanism exists -- `migrate_many_atomically` decrypts, chain-upgrades and
replaces atomically -- so the migration is buildable. It would rewrite every
encrypted row in every namespace, on a surface governed by
`sensitive-financial-data-secure-storage-only`, and it needs a transition rule
for rows read before they are restamped. That is the operator's call.

### The risk the step implies does not exist

A delimiter join is unsafe when a field can contain the delimiter. Seven of the
eight inputs cannot by construction: a hex object key, a decimal schema version,
an ISO-8601 instant, and four hex digests or empty strings. Only `namespace` is
typed loosely, as `str = Field(min_length=1)`.

The first reading was that this leaves a forgery open, and a probe was written
to prove it. The probe FAILED, and working out why is the finding: injecting the
delimiter into `namespace` shifts content into `object_key.hex()`, whose
alphabet is hex digits. There is no valid second tuple that re-parses the same
joined string, because the field that would have to absorb the overflow cannot
legally hold it. Every valid tuple carries exactly seven delimiters; an injected
one carries more, and hashes differently.

So the existing derivation is injective, and the migration would buy the same
property at the cost of restamping every stored row.

### What was done instead

The safety rested on every declared namespace happening to be a plain
identifier -- true of all 77, but a convention rather than an invariant. It is
now a gate, with the injectivity argument asserted alongside it rather than left
in a comment, so a future namespace that breaks the property fails a test rather
than silently weakening a tamper check.

The step stays open: this closes the risk, not the step. Whether to adopt the
canonical primitive anyway, for one-mechanism reasons rather than safety ones,
is the persisted-format decision above.
