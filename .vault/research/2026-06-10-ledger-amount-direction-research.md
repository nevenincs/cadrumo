---
tags:
  - '#research'
  - '#ledger-amount-direction'
date: '2026-06-10'
modified: '2026-06-10'
related: []
---



# `ledger-amount-direction` research: `Ledger amount/direction convention`

This research grounds the canonical encoding of a ledger transaction's
*flow*: how a row records whether money came in, went out, or moved between
the taxpayer's own accounts. The codebase today carries a redundant hybrid —
a *signed* `amount` plus a parallel `direction` enum — where the two encode
the same fact in two places that can disagree, are enforced unevenly across
the import and manual paths, and are already discarded in favour of
`direction` everywhere arithmetic actually happens. This document inventories
the current state so the sibling ADR can ratify a single source of truth.
It belongs to cluster **C1** of the ledger amount/direction restructure and
defines the non-negative-amount + direction contract that downstream clusters
**C5** (list rows) and **C7** (participation / evidence projections) consume.

## Findings

### F1 — The store is a signed-amount + redundant-direction hybrid

`RawTransaction.amount` (`src/aeat/domain/transactions/_raw_transaction.py`)
is a bare `Decimal` documented as "Signed", negative for an expense and
positive for income. The wrapping `Transaction`
(`src/aeat/domain/transactions/_models.py`) carries a separate closed
`direction: TransactionDirection` (INCOMING / OUTGOING / INTERNAL_TRANSFER).
Two fields encode one fact. Nothing structurally binds the sign of
`raw.amount` to `direction` on the `Transaction` model: `Transaction` has
**no** sign↔direction validator. The redundancy is the root problem — two
representations of flow that can drift apart.

### F2 — Sign↔direction consistency is enforced only on the manual path

`ManualLedgerTransactionCommand._validate_direction_policy`
(`src/aeat/application/ledger/_models.py`, around lines 173–185) is the
**only** place that enforces agreement: it rejects a zero amount, requires a
negative amount for OUTGOING, a positive amount for INCOMING, and a separate
payload shape for INTERNAL_TRANSFER. Its coverage is verified by
`src/aeat/application/ledger/tests/test_models.py` (around lines 136–153).
This validator lives on the *manual command*, not on the domain `Transaction`,
so any path that builds a `Transaction` without going through the manual
command escapes it.

### F3 — The import path derives direction from sign and skips the gate (zero-amount bug)

`_direction_from_amount` (`src/aeat/application/ledger/_actions_common.py`,
around line 127) returns `OUTGOING if raw.amount < 0 else INCOMING`. The
import action (`src/aeat/application/ledger/_actions_import.py`, around lines
333 and 359) passes this resolver into both the dry-run preview and the
persisting import. Two consequences: (a) the import path never invokes the
manual validator, so its consistency is enforced only by construction, not by
the schema; and (b) a **zero-amount** row resolves to INCOMING — a silent
misclassification with no operator signal, where the manual path would reject
the same row. INTERNAL_TRANSFER cannot be expressed by sign at all, so an
import has no way to emit it.

### F4 — Direction is already the load-bearing routing key; sign is already discarded in arithmetic

Aggregation everywhere takes the magnitude and routes on `direction`:

- IVA aggregation (`src/aeat/application/iva/_iva_ledger.py`) routes purely
  by `direction`.
- Renta aggregation (`src/aeat/application/renta/_renta_ledger.py` and
  `_renta_income_ledger.py`) uses `abs()` on the amount.

So the sign already carries no arithmetic information downstream — it is a
redundant copy of a fact `direction` already holds authoritatively. Removing
the sign loses nothing the calculation engines read.

### F5 — Evidence rows carry both signed amount and direction; value_in_eur is already non-negative

`LedgerEvidenceRow`
(`src/aeat/domain/modelos/_ledger_filing_snapshot.py`, around lines 144–168)
carries both a signed `amount` and `direction` — the same redundancy at the
evidence boundary. Notably `value_in_eur` is **already** stored non-negative
on the live import path: `_actions_import.py` (around lines 134–137) stamps
`abs(result.eur_amount)`, and `Transaction._validate_fx_fields`
(`_models.py`) already rejects a negative `value_in_eur`. So the EUR
projection is already absolute; only `raw.amount` and the evidence-row
`amount` still carry a sign. The evidence roundtrip fixture
(`src/aeat/domain/modelos/tests/test_ledger_filing_evidence_roundtrip.py`,
around lines 40–68) hard-codes `amount=Decimal("-121.00")` and
`value_in_eur=Decimal("-112.04")` — the fixture is the only place a negative
evidence `value_in_eur` is constructed, and it must move to non-negative +
authoritative direction.

### F6 — The snapshot fingerprint depends on raw.amount

The per-contributor fingerprint feeding `LedgerFilingSnapshot`
(`src/aeat/domain/modelos/_ledger_filing_snapshot.py`) and the transaction id
itself (`derive_transaction_id`, `_models.py`, which hashes
`canonical_decimal_string(raw.amount)`) both fold `raw.amount` into a content
hash. Changing the stored amount from `-121.00` to `121.00` changes every
fingerprint and every derived id. Under the project's pre-beta zero-legacy
posture this is acceptable: there is no released data, so old fingerprints
and ids are simply absent, never migrated.

### F7 — Split children must currently share the parent's sign

`_validate_split_child_amounts`
(`src/aeat/application/ledger/_actions_split_merge.py`, around lines 289–329)
requires every child amount to be non-zero and to *share the parent's sign*
(`(child.amount < 0) != parent_negative` raises). The `SplitChildCommand`
docstring (`_models.py`, around lines 401–415) states "positive for INCOMING,
negative for OUTGOING". Children inherit the parent's `direction` already
(the split builder copies `parent.direction`), so "share the sign" is a
sign-encoded restatement of "share the direction". INTERNAL_TRANSFER has no
defined sign rule in the split path today.

### F8 — Docs and the CLI encode the sign convention

`docs/how-to/import-bank-statements.md` (around lines 72, 82, 88) instructs
the operator to pass `--amount=-49.99` for an expense and `--amount 121.00`
for income, pairing the sign with `--direction`. The CLI `add` command
(`src/aeat/entrypoints/cli/_ledger.py`, around lines 376 and 443) accepts
`--amount` as a free `str` parsed by `_parse_required_decimal` with no
non-negativity guard, so a negative magnitude flows straight through to the
manual command's sign check.

### F9 — Secure-storage posture (unchanged by this change)

Every ledger artefact already rides the per-profile encrypted Secure Storage
backend: the transaction catalogue and bucket-event history persist through a
bucket-scoped `SecureObjectRepository`
(`secure_object_repository_for_bucket` in
`src/aeat/application/ledger/_actions_common.py`), and the evidence /
fingerprint snapshot rides inside the encrypted `CalculationRevision`
envelope. This change alters *field values and validators* on those records;
it does not introduce any new on-disk artefact and does not move any data
outside the encrypted namespace. No plaintext financial data is created or
relocated.

### F10 — Governing rules and prior ADRs

- `aeat-calculation-grounding` — provenance (legal_refs / source_refs) must
  survive every boundary; this change must not drop them from the evidence
  row.
- `ledger-derived-revisions-bundle-evidence` — the evidence row must
  reconstitute the casilla basis; a non-negative amount + authoritative
  direction must still re-derive the same routed value.
- `aeat-roundtrip-discipline` — every persistence boundary needs a strict
  save→load→equality roundtrip with non-default fields plus an anti-tautology
  proof.
- `no-legacy-compatibility` — pre-beta, no released data; delete the signed
  encoding outright and refuse old shapes on load, no migration / bridge.
- Prior ADRs: `2026-05-14-ledger-transaction-lifecycle-adr` (split-sum
  integrity) and `2026-05-08-ledger-renta-pipeline-adr` (the renta `abs()`
  aggregation path).

### F11 — Summary of the redundancy

`direction` is already the authoritative routing axis; sign is a redundant,
unevenly-enforced second copy that the arithmetic discards. The natural
resolution is to keep the magnitude (absolute, non-negative) and make
`direction` the single source of truth for flow — removing the sign from
storage entirely.
