---
name: ledger-amount-is-absolute-direction-is-authority
---

# Ledger amount is an absolute magnitude; direction is the sole flow authority

## Rule

A ledger transaction stores a **non-negative** `amount` magnitude; flow
direction is carried solely by the `direction` enum (INCOMING / OUTGOING /
INTERNAL_TRANSFER). No model, adapter, evidence row, or CLI surface may encode
flow in the sign of an amount. The non-negative constraint is enforced at the
`RawTransaction` boundary so the import and manual paths are both gated, and the
evidence-row `amount` / `value_in_eur` mirror that absolute convention. There is
no signed-amount shape to read, migrate, or bridge — old is deleted, not
tolerated (`no-legacy-compatibility`).

## Why

Flow was encoded twice — as the sign of a `Decimal` amount and, redundantly, as
a parallel `direction` enum — and the two could disagree. Consistency was
enforced only on the manual command; the import path derived direction from the
sign and skipped the gate, so a zero-amount import silently classified as
INCOMING. Every aggregation engine already routes on `direction` and takes
`abs()` of the amount (the sign carried no arithmetic signal), and `value_in_eur`
was already stored non-negative. The `2026-06-10-ledger-amount-direction-adr`
collapsed flow onto the single authoritative `direction`, removed the sign from
storage, and closed the enforcement gap with one model-level gate. This is the
ledger-encoding counterpart of `aeat-calculation-grounding` (provenance —
including `direction` — survives every boundary) and `no-silent-under-declaration`
(the zero-amount misclassification was a silent error a shared gate now refuses).

## How

- **Good:** `RawTransaction.amount` carries a non-negative validator that raises
  `TransactionValidationError` on a negative value; it fires whether the row is
  built by an import adapter or by `ManualLedgerTransactionCommand`. A
  save→load→equality roundtrip plus an anti-tautology proof (corrupt the on-disk
  amount to a negative, assert refusal at load) lock the boundary.
- **Good:** an import adapter maps the bank export's sign (or native debit/credit
  signal) to a `TransactionDirection` **at the parse boundary** and stores
  `abs(amount)`, yielding a typed `ParsedLedgerRow(raw, direction)`; the import
  action carries that explicit `direction` onto the `Transaction` and never
  re-derives flow from a sign. A zero-amount source row is refused at the parse
  boundary, consistent with the manual path.
- **Good:** `INTERNAL_TRANSFER` is stored as a magnitude paired with
  `direction = INTERNAL_TRANSFER`; split children store magnitudes and inherit
  the parent's `direction`; the reconciliation matcher routes by direction
  (RECEIVED↔OUTGOING, ISSUED↔INCOMING) and matches on the magnitude.
- **Good:** the CLI `--amount` refuses a negative magnitude with an instructive,
  localised error that names the accepted form (a non-negative amount plus
  `--direction`), never a bare "value invalid".
- **Bad:** writing a negative amount to encode an expense, or a
  `direction_from_amount` helper that reads `raw.amount < 0` downstream of the
  parse boundary — flow lives in `direction`, and there is no sign to read.
- **Bad:** a read-tolerance branch that coerces a legacy signed-amount record on
  load, or a migration that flips old fingerprints — there is no released data;
  old shapes are absent, refused, never bridged.

## Source

ADR `2026-06-10-ledger-amount-direction-adr` (accepted); research
`2026-06-10-ledger-amount-direction-research`; plan
`2026-06-10-ledger-amount-direction-plan` (cluster C1). Companion rules:
`aeat-calculation-grounding`, `no-silent-under-declaration`,
`no-legacy-compatibility`, `ledger-derived-revisions-bundle-evidence`.
