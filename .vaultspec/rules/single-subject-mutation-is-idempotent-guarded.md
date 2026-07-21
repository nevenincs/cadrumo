---
name: single-subject-mutation-is-idempotent-guarded
---

# Single-subject creating mutations are idempotent-guarded

## Rule

Every CLI verb (and the application service behind it) that CREATES one
addressable record MUST be `idempotent_guarded`: a retry carrying the same
caller-supplied idempotency key — or the same deterministic, clock-free derived
id — returns the EXISTING record as a no-op (no second lifecycle event, no
`created_at`/`modified_at` re-stamp, no re-run of side effects) surfaced through
the surface's uniform result shape (e.g. the ledger mutation quintet with empty
`bucket_event_ids`) plus an info `Notice`; a same-key call whose content DIFFERS
refuses with an instructive, localised conflict naming the divergent fields. A
verb that is deliberately additive (two genuinely-distinct records may share
identical content) is `non_idempotent_append` and MUST document that choice. The
record's identity MUST be clock-free — the timestamp is a non-identity last-seen
body field, never folded into the derived id — so a retry at a different instant
resolves to the same record.

## Why

Per ADR `2026-06-30-ledger-add-idempotency-adr`, the `aeat` CLI's operator is an
autonomous LLM agent that retries calls, so a non-retry-safe creating mutation
silently double-writes (a duplicate ledger transaction inflates every downstream
modelo aggregation; a time-stamped verify/filing record accumulates one copy per
retry). It closed this across manual `ledger add`, `modelo verify`, and `modelo
file` by keying on a clock-free id and refusing same-key/different-content; the
close review `2026-07-01-ledger-add-idempotency-audit` caught the guarded failure
mode — a no-op match that omits a field (recargo, source jurisdiction) silently
drops the new value (`no-silent-under-declaration`).

## How

- **Good:** `create_manual_transaction` keys on the clock-free provider id
  `manual:{bucket}:{key}`; a same-key retry with matching content returns the
  existing-row quintet with empty `bucket_event_ids` + an info `Notice`, emitting no
  second `LEDGER_TRANSACTION_CREATED` event and leaving `created_at` unchanged; a
  differing same-key add raises `TransactionValidationError`. The match compares
  EVERY persisted field (including `recargo_amount` and `source_jurisdiction`).
- **Good:** `derive_verification_report_id` / `derive_filing_record_id` fold the
  OUTCOME (revision + status/findings + actor) and drop the timestamp from identity;
  a non-granting verify retry and a re-file of an already-`PRESENTADO` revision
  collapse to the existing record with an info `Notice`.
- **Good:** the keyless `ledger add` path stays `non_idempotent_append` (two genuine
  identical same-day cash movements both persist); the agent-harness contract
  requires the agent to always pass a stable idempotency key.
- **Bad:** an id that folds `now()`/`occurred_at`/`filed_at` (a retry mints a new id
  and double-writes), or a guarded no-op whose match omits a persisted field so a
  same-key retry changing only that field silently drops the new value.
- **Bad:** modelling a deliberately-additive verb as guarded (collapsing distinct
  records) or an idempotent verb as append (double-writing on retry) without
  documenting the choice.

## Source

ADR `2026-06-30-ledger-add-idempotency-adr`; audit `2026-07-01-ledger-add-idempotency-audit`.
Companion: `ledger-mutation-returns-uniform-quintet`,
`cli-single-subject-id-is-positional`, `cli-notices-are-the-only-diagnostic-channel`,
`no-silent-under-declaration`.
