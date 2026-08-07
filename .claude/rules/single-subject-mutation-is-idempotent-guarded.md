---
name: single-subject-mutation-is-idempotent-guarded
trigger: always_on
---

# Single-subject creating mutations are idempotent-guarded

## Rule

Every CLI verb — and the application service behind it — that CREATES one
addressable record MUST be `idempotent_guarded`: a retry carrying the same
caller-supplied idempotency key, or the same deterministic clock-free derived
id, returns the EXISTING record as a no-op (no second lifecycle event, no
`created_at` / `modified_at` re-stamp, no re-run of side effects), surfaced
through the surface's uniform result shape plus an info `Notice`. A same-key call
whose content DIFFERS refuses with an instructive, localised conflict naming the
divergent fields.

A verb that is deliberately additive — where two genuinely distinct records may
share identical content — is `non_idempotent_append` and MUST document that
choice.

**The record's identity MUST be clock-free.** The timestamp is a non-identity
last-seen body field, never folded into the derived id, so a retry at a different
instant resolves to the same record.

## Why

This CLI's operator is an autonomous agent that retries calls, so a
non-retry-safe creating mutation silently double-writes: a duplicate ledger
transaction inflates every downstream modelo aggregation, and a time-stamped
verify or filing record accumulates one copy per retry.

The guarded failure mode is subtler: a no-op match that omits a field silently
drops the new value, which is a `no-silent-under-declaration` breach wearing the
clothes of a successful retry.

## How

- **Good:** a manual transaction keys on a clock-free provider id; a same-key
  retry with matching content returns the existing-row result with an empty
  event list plus an info `Notice`, emitting no second lifecycle event and
  leaving `created_at` unchanged. A differing same-key call raises. **The match
  compares EVERY persisted field.**
- **Good:** derived verification and filing record ids fold the OUTCOME —
  revision, status or findings, actor — and drop the timestamp from identity, so
  a non-granting verify retry and a re-file of an already-presented revision
  collapse to the existing record.
- **Good:** a keyless append path stays `non_idempotent_append` (two genuine
  identical same-day cash movements both persist), and the agent-harness
  contract requires the agent to always pass a stable idempotency key.
- **Bad:** an id that folds the clock — a retry mints a new id and double-writes.
- **Bad:** a guarded no-op whose match omits a persisted field, so a same-key
  retry changing only that field silently drops the new value.
- **Bad:** modelling a deliberately additive verb as guarded, or an idempotent
  verb as append, without documenting the choice.

## Source

ADR `2026-06-30-ledger-add-idempotency-adr`; audit
`2026-07-01-ledger-add-idempotency-audit`. Companions:
`ledger-mutation-returns-uniform-quintet`,
`cli-single-subject-id-is-positional`,
`cli-notices-are-the-only-diagnostic-channel`,
`no-silent-under-declaration`.
