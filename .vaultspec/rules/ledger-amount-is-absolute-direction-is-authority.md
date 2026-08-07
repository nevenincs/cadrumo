# Ledger amount is an absolute magnitude; direction is the sole flow authority

A ledger transaction stores a **non-negative** `amount` magnitude; flow direction
is carried solely by the `direction` enum (INCOMING / OUTGOING /
INTERNAL_TRANSFER). No model, adapter, evidence row or CLI surface may encode
flow in the sign of an amount. The non-negative constraint is enforced at the
`RawTransaction` boundary so import and manual paths are both gated, and evidence
rows mirror the absolute convention.

There is no signed-amount shape to read, migrate or bridge — old is deleted, not
tolerated.

Flow was once encoded twice, as the sign of the amount and redundantly as the
enum, and the two could disagree. Consistency was enforced only on the manual
command, so the import path derived direction from the sign and a zero-amount
import silently classified as INCOMING. Every engine already routes on
`direction` and takes the absolute value.

## How

- **Good:** `RawTransaction.amount` carries a non-negative validator raising a
  typed validation error, firing for both import adapters and the manual command,
  locked by a save-load-equality roundtrip plus an anti-tautology proof (corrupt
  the on-disk amount negative, assert load refusal). Import adapters map the
  export sign or debit/credit signal to a direction at the parse boundary, store
  the absolute amount, and refuse a zero-amount source row; the import action
  carries that explicit direction and never re-derives flow. Internal transfers
  and split children store magnitudes; the reconciliation matcher routes by
  direction. The CLI refuses a negative magnitude with an instructive localised
  error naming the accepted form.
- **Bad:** writing a negative amount to encode an expense; a
  `direction_from_amount` helper reading `amount < 0` downstream of the parse
  boundary; or a read-tolerance branch coercing a legacy signed-amount record.

Source: ADR `2026-06-10-ledger-amount-direction-adr`. Companions:
`no-legacy-compatibility`, `no-silent-under-declaration`.
