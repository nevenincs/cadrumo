---
tags:
  - '#adr'
  - '#ledger-amount-direction'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - "[[2026-06-10-ledger-amount-direction-research]]"
---



# `ledger-amount-direction` adr: `Ledger absolute-amount + direction-authority convention` | (**status:** `accepted`)

## Problem Statement

A ledger transaction's *flow* — money in, money out, or a transfer between the
taxpayer's own accounts — is encoded twice today: as the **sign** of a
`Decimal` amount and, redundantly, as a parallel `direction` enum. The two can
disagree, are enforced unevenly (the manual command validates the pairing; the
import path derives one from the other and skips the validator), and the sign
is already discarded by every aggregation engine, which routes on `direction`
and takes `abs()` of the amount. The redundancy is a correctness hazard
(a zero-amount import silently classifies as INCOMING) and a maintenance tax
(every new consumer must remember the sign convention). The
`[[2026-06-10-ledger-amount-direction-research]]` inventory (F1–F11) grounds
this. This ADR ratifies the locked decision for cluster **C1** of the ledger
restructure: store an **absolute amount** plus an **authoritative direction**,
and remove the sign from storage entirely.

## Considerations

- **Direction is already authoritative.** Research F4: IVA aggregation routes
  purely by `direction`; renta aggregation uses `abs()`. The sign carries no
  arithmetic signal downstream. Promoting `direction` to sole authority loses
  nothing the engines read.
- **The enforcement gap is the real bug.** Research F2–F3: consistency is
  enforced only on the manual path; the import path can emit a zero-amount row
  as INCOMING. A single gate that fires on both paths closes this.
- **EUR projection is already absolute.** Research F5: `value_in_eur` is
  already stored non-negative and the FX validator already rejects negatives.
  Only `raw.amount` and the evidence-row `amount` still carry a sign; the rest
  of the change is making those two consistent with the already-absolute EUR
  field.
- **Zero-legacy posture removes the migration question.** Per
  `no-legacy-compatibility`, this is a pre-beta project with no released data.
  Changing the stored amount changes fingerprints and derived ids (research
  F6), but there is nothing to migrate — old shapes are deleted and refused,
  not bridged.
- **Cross-cluster contract.** C5 (list rows) and C7 (participation / evidence
  projections) will carry the non-negative-amount + direction shape this ADR
  defines; C6 (filter) is unaffected.

## Constraints

- **Fingerprint / id recomputation.** `derive_transaction_id` and the
  `LedgerFilingSnapshot` per-contributor fingerprint both fold `raw.amount`
  into a content hash (research F6). Storing the absolute amount changes every
  digest. This is in-scope and acceptable: there is no released data, so old
  fingerprints and ids are simply *absent* — never read, never migrated. No
  read-tolerance branch for a signed-amount record is permitted.
- **No external dependencies.** The change is internal to the transaction and
  modelo-evidence domains plus the ledger application and CLI layers. It
  depends on no immature or frontier library.
- **Parent-feature stability.** It builds on two stable accepted decisions —
  `2026-05-14-ledger-transaction-lifecycle-adr` (split-sum integrity) and
  `2026-05-08-ledger-renta-pipeline-adr` (renta `abs()` aggregation). Both are
  landed and unchanged in posture; this ADR refines the encoding they consume,
  not their behaviour.
- **Provenance must survive.** Per `aeat-calculation-grounding` and
  `ledger-derived-revisions-bundle-evidence`, the evidence row must keep its
  `legal_refs` / `source_refs` and must still re-derive the same routed
  casilla value from the absolute amount + direction.

## Implementation

The canonical convention becomes: **`amount` is a non-negative magnitude;
`direction` (INCOMING / OUTGOING / INTERNAL_TRANSFER) is the single source of
truth for flow.** The sign is removed from storage. The decision settles each
point the research surfaced:

- **D1 — Model fields gain a non-negative gate.** `RawTransaction.amount`
  gains a non-negative constraint (a `ge=0`-equivalent validator that raises
  the typed `TransactionValidationError`), and `RawTransaction`'s docstring
  drops the "Signed" language. The validator lives on `RawTransaction` so it
  fires whether the row is built by import or by the manual command (D8). The
  manual command's `_validate_direction_policy` is rewritten: it no longer
  couples sign to direction (there is no sign), keeps the zero-amount
  rejection, and keeps the INTERNAL_TRANSFER payload-shape check.

- **D2 — Import supplies an explicit direction at the boundary.** The import
  path stops deriving direction from sign inside the domain. The import adapter
  maps the bank export's sign (or its native debit/credit signal) to a
  `direction` **at the parse boundary**, then stores the absolute magnitude.
  `_direction_from_amount` is replaced by an explicit direction supplied by the
  parser/provider; a **zero-amount** row is **rejected** at import (consistent
  with the manual path), never silently classified. A genuine sign-bearing
  bank export has its sign consumed once, at the adapter, to choose the
  direction, and is then discarded.

- **D3 — INTERNAL_TRANSFER.** Stored as an absolute amount with
  `direction = INTERNAL_TRANSFER`. It carries no INCOMING/OUTGOING analog and
  routes to neither an income nor an expense base — the aggregation layers
  already exclude it from tax-relevant sums (its payload-shape gate forbids
  tax/evidence fields). The absolute-amount rule applies uniformly: transfers
  store magnitude, never a sign.

- **D4 — Evidence row becomes non-negative; direction authoritative.**
  `LedgerEvidenceRow.amount` and `value_in_eur` become non-negative (the EUR
  field already is, research F5); `direction` is the authoritative flow field.
  The roundtrip fixture that constructs `amount=-121.00` /
  `value_in_eur=-112.04` is updated to non-negative magnitudes paired with
  `direction = OUTGOING`.

- **D5 — Fingerprints recompute, old ones absent.** Because `raw.amount`
  storage changes, every transaction id and snapshot fingerprint changes. Under
  zero-legacy this is fine: old fingerprints are simply not present; nothing
  reads or migrates them.

- **D6 — Split children share DIRECTION, not sign.** The split-child validator
  drops the "share the parent's sign" check and asserts children inherit the
  parent's `direction` (they already do). The `SplitChildCommand` docstring is
  updated to "absolute magnitude; direction inherited from the parent". The
  child sum-equals-parent integrity check is preserved (it operates on
  non-negative magnitudes).

- **D7 — CLI rejects a negative magnitude instructively.** `--amount` accepts
  only a non-negative magnitude; a negative input is refused with a localised,
  instructive error that names the accepted form (per
  `aeat-architecture-boundaries`: the refusal lists the accepted shape — pass a
  non-negative amount and set `--direction`). `docs/how-to/import-bank-statements.md`
  is rewritten to drop the `-`-prefix convention and instruct the operator to
  pass a magnitude plus `--direction OUTGOING` / `INCOMING`.

- **D8 — One gate on both paths.** The non-negative `amount` validator on
  `RawTransaction` (D1) gates import and manual paths alike, eliminating the
  manual-only enforcement gap (research F2–F3).

- **D9 — Roundtrip + anti-tautology tests.** Per `aeat-roundtrip-discipline`:
  a strict save→load→equality roundtrip for the evidence row and the
  transaction record with every defaultable field populated non-default, plus
  an anti-tautology proof (mutate the on-disk payload to a negative amount,
  reload, assert a `ValidationError` is raised) so a regression that re-admits
  a signed amount fails loudly.

### Secure-storage gate

This change touches the field values and validators of records that already
ride the per-profile encrypted Secure Storage backend; it introduces **no new
on-disk artefact** and moves **no** financial data outside an encrypted
bucket-scoped namespace. The persisted artefacts touched:

- **Transaction catalogue rows** (the `Transaction` wrapping `RawTransaction`,
  whose `amount` becomes absolute). Persisted through the bucket-scoped
  `SecureObjectRepository` obtained via `secure_object_repository_for_bucket`
  in the ledger application layer — an encrypted, registered secure-object
  namespace.
- **Bucket-event history** (the lifecycle/split/import events recording the
  rows). Persisted through the same bucket-scoped `SecureObjectRepository`.
- **Ledger filing evidence** (`LedgerEvidenceRow` whose `amount` /
  `value_in_eur` become non-negative, plus the snapshot fingerprint that
  recomputes). Bundled inside the encrypted `CalculationRevision` envelope,
  which persists through the per-profile encrypted Secure Storage backend.

No plaintext financial data is written to disk by this change. Every artefact
above remains enrolled in its existing encrypted bucket-scoped namespace; the
change is confined to the in-memory typed shape and the validators that gate
it at the boundary.

## Rationale

The research (F4, F11) shows `direction` is already the load-bearing routing
key and the sign is a redundant second copy the arithmetic discards. Keeping
both invites drift and forces every consumer to learn a sign convention that
buys nothing; the uneven enforcement (F2–F3) has already produced a real
zero-amount misclassification bug. Collapsing flow onto a single authoritative
`direction` and storing magnitude is the minimal change that removes the
redundancy, closes the enforcement gap with one model-level gate, and aligns
`amount` with the already-absolute `value_in_eur` (F5). The zero-legacy posture
(`no-legacy-compatibility`) makes the fingerprint churn (F6) a non-issue — there
is no released data to preserve — so the cleanest path is to delete the signed
encoding rather than bridge it.

## Consequences

- **Gain:** one authoritative flow field; impossible to construct a row whose
  sign and direction disagree, because there is no sign. The zero-amount import
  bug is closed by the shared model gate.
- **Gain:** `amount` and `value_in_eur` are now uniformly non-negative; a
  reader no longer has to remember which fields are signed.
- **Cost:** every transaction id and snapshot fingerprint changes value. Benign
  under zero-legacy (no released data), but any in-repo test fixture that pins a
  specific fingerprint/id derived from a signed amount must be regenerated in
  the same atomic change.
- **Cost:** the import adapters must now produce an explicit `direction` from
  their native debit/credit or sign signal at the parse boundary, rather than
  leaning on a downstream sign-to-direction derivation. This is a small, local
  adapter change but must be done for every supported `SourceFormat`.
- **Pitfall:** INTERNAL_TRANSFER has no income/expense routing analog; care is
  needed that no aggregation path treats a transfer's magnitude as a base — the
  existing payload-shape gate already enforces this and must be kept.
- **Pathway:** C5 (list rows) and C7 (participation / evidence projections) can
  now consume a single, uniformly non-negative amount + authoritative direction
  contract without re-deriving sign semantics. C6 (filter) is unaffected.

## Codification candidates

- **Rule slug:** `ledger-amount-is-absolute-direction-is-authority`.
  **Rule:** A ledger transaction stores a non-negative `amount` magnitude;
  flow direction is carried solely by the `direction` enum (INCOMING /
  OUTGOING / INTERNAL_TRANSFER), and no model, adapter, evidence row, or CLI
  surface may encode flow in the sign of an amount — the non-negative
  constraint is enforced at the `RawTransaction` boundary so import and manual
  paths are both gated.
