# Single-subject CLI verbs: positional id, uniform result, idempotent-guarded

## The subject id is positional

A verb that addresses one ledger transaction accepts the id as a positional
`Argument` resolved through the single shared transaction-id resolver — never as
a `--id` option, and never through a duplicated `_resolve_id` helper. The subject
is an argument; flags configure the operation. An optional single-subject verb
still uses an optional positional where the semantics genuinely allow no subject.

## Single-transaction mutations return the uniform quintet

Every CLI verb that mutates exactly one ledger transaction returns
`{bucket_id, transaction_id, bucket_event_ids, review_status, transaction}`
through the shared ledger mutation result shape, so operators and downstream
automation read one envelope for the changed subject, its review state, and its
emitted events.

Structural verbs that act on a set or destroy the subject (`split`, `merge`,
`remove`, `reset`) are different operations and declare their own typed schemas
explicitly.

## How

- **Bad:** a single-transaction mutation returning only `transaction_id`, or
  duplicating the quintet fields in an ad-hoc payload.

## Creating mutations are idempotent-guarded

Every verb — and the service behind it — that CREATES one addressable record MUST
be `idempotent_guarded`: a retry carrying the same caller-supplied idempotency
key, or the same deterministic clock-free derived id, returns the EXISTING record
as a no-op (no second lifecycle event, no `created_at`/`modified_at` re-stamp, no
re-run of side effects), surfaced through the uniform result shape plus an info
`Notice`. A same-key call whose content DIFFERS refuses with an instructive,
localised conflict naming the divergent fields.

A verb that is deliberately additive — two genuinely distinct records may share
identical content — is `non_idempotent_append` and MUST document that choice.

**Identity MUST be clock-free.** The timestamp is a non-identity last-seen body
field, never folded into the derived id, so a retry at a different instant
resolves to the same record.

This CLI's operator is an autonomous agent that retries calls, so a
non-retry-safe creating mutation silently double-writes: a duplicate ledger
transaction inflates every downstream modelo aggregation. The subtler failure is
a **no-op match that omits a persisted field**, which silently drops the new
value — a `no-silent-under-declaration` breach wearing the clothes of a
successful retry. **The match compares EVERY persisted field.**

## How

- **Good:** derived verification and filing record ids fold the OUTCOME (revision,
  status or findings, actor) and drop the timestamp, so a non-granting verify
  retry and a re-file of an already-presented revision collapse to the existing
  record.
- **Bad:** an id that folds the clock; a guarded no-op whose match omits a field;
  or modelling a deliberately additive verb as guarded without documenting it.

Source: ADRs `2026-06-10-ledger-interface-contract-adr`,
`2026-06-30-ledger-add-idempotency-adr`. Companion:
`cli-notices-are-the-only-diagnostic-channel`.
