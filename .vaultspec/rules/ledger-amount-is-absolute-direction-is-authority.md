---
name: ledger-amount-is-absolute-direction-is-authority
---

# Ledger amount is an absolute magnitude; direction is the sole flow authority

## Rule

A ledger transaction stores a **non-negative** `amount` magnitude; flow direction
is carried solely by the `direction` enum (INCOMING / OUTGOING /
INTERNAL_TRANSFER). No model, adapter, evidence row, or CLI surface may encode
flow in the sign of an amount. The non-negative constraint is enforced at the
`RawTransaction` boundary so import and manual paths are both gated, and the
evidence-row `amount` / `value_in_eur` mirror the absolute convention. There is
no signed-amount shape to read, migrate, or bridge — old is deleted, not tolerated
(`no-legacy-compatibility`).

## Why

Flow was encoded twice — as the sign of a `Decimal` amount and, redundantly, as a
`direction` enum — and the two could disagree; consistency was enforced only on
the manual command, so the import path derived direction from the sign and a
zero-amount import silently classified as INCOMING. Every engine already routes on
`direction` and takes `abs()`. ADR `2026-06-10-ledger-amount-direction-adr`
collapsed flow onto `direction`, removed the sign from storage, and closed the gap
with one model-level gate.

## How

- **Good:** `RawTransaction.amount` carries a non-negative validator raising
  `TransactionValidationError`, firing for both import adapters and
  `ManualLedgerTransactionCommand`, locked by a save→load→equality roundtrip plus
  an anti-tautology proof (corrupt the on-disk amount negative, assert load
  refusal). Import adapters map the export sign / debit-credit signal to a
  `TransactionDirection` at the parse boundary and store `abs(amount)` as a typed
  `ParsedLedgerRow(raw, direction)`, refusing a zero-amount source row; the import
  action carries that explicit `direction` and never re-derives flow.
  `INTERNAL_TRANSFER` and split children store magnitudes; the reconciliation
  matcher routes by direction (RECEIVED↔OUTGOING, ISSUED↔INCOMING). The CLI
  `--amount` refuses a negative magnitude with an instructive localised error
  naming the accepted form, never a bare "value invalid".
- **Bad:** writing a negative amount to encode an expense; a `direction_from_amount`
  helper reading `raw.amount < 0` downstream of the parse boundary; or a
  read-tolerance / migration branch coercing a legacy signed-amount record — there
  is no released data, old shapes are absent and refused, never bridged.

## Source

ADR `2026-06-10-ledger-amount-direction-adr`; research/plan same stem (cluster
C1). Companion: `aeat-calculation-grounding`, `no-silent-under-declaration`,
`no-legacy-compatibility`, `ledger-derived-revisions-bundle-evidence`.
