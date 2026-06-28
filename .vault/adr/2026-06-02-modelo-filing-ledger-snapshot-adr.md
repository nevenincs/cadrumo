---
tags:
  - '#adr'
  - '#modelo-filing-ledger-snapshot'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-ledger-operator-hardening-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
  - "[[2026-05-14-ledger-transaction-lifecycle-adr]]"
  - '[[2026-06-04-modelo-filing-ledger-snapshot-research]]'
---



# `modelo-filing-ledger-snapshot` adr: `modelo filing revisions are backed by an immutable ledger snapshot` | (**status:** `accepted`)

## Problem Statement

Today a `CalculationRevision` links to the ledger only by *live reference*:
`source_transaction_ids` names the contributing rows, and once a revision reaches
`VERIFICADO_COMPLETO` / `PRESENTADO` / `PRESENTADO_SUPERSEDIDO` the guard
`_blocking_modelo_references` refuses mutation of those rows. Integrity rests
entirely on the block holding. There is (1) no immutable capture of the ledger
row *values* at filing time, (2) no way to detect that a filed modelo has drifted
from the ledger state it was computed against, and (3) no uniform provenance:
only ledger-fed modelos (303/130/100/OSS) carry `source_transaction_ids`, so
390/347/036 and others have no ledger-state linkage at all. A filed return must
be provably tied to the exact ledger state that produced it -- a human files it
with AEAT, and the audit trail must reconstruct "these numbers came from this
ledger state" for every modelo, indefinitely.

## Considerations

- The contributing rows are already immutable-by-block, but a block is not an
  audit record: it cannot reconstruct historical values, cannot detect a
  bypass, and emits no staleness signal. Snapshot backing adds auditability and
  staleness on top of (not instead of) the block.
- Uniformity must be structural: the feature has to attach to *every* modelo
  filing, not only ledger-fed ones. A non-ledger modelo simply gets an
  empty-but-valid snapshot (the fingerprint of the empty contributor set), so the
  linkage field is universal and never special-cased per modelo code.
- The snapshot must be deterministic and content-addressed: a SHA-256 over the
  canonical serialization of each contributor's tax-relevant facts, so an
  identical ledger state always yields an identical snapshot id, and any change
  to a contributing fact changes the fingerprint.
- Backward compatibility: already-persisted revisions have no snapshot; an absent
  snapshot must read as "legacy, unsnapshotted" and never crash load.

## Constraints

- Must integrate with the existing `calculate -> verify -> file` flow and the
  `CalculationRevision` / `ModeloRecord` / `WorkUnit` records without breaking
  the deterministic `derive_calculation_revision_id` hash or existing roundtrips.
- Must persist through the encrypted `SecureObjectRepository` boundary as strict
  pydantic v2 (per architecture boundaries and roundtrip discipline).
- Parent features are stable and accepted: the renta/iva aggregation pipelines,
  the calculation-revision lifecycle, and the transaction-lifecycle/edit-lineage
  model. This ADR builds on the existing `source_transaction_ids` linkage rather
  than replacing it.
- Storage must stay bounded: persist per-contributor *fingerprints* plus the
  aggregate snapshot fingerprint, not a second full copy of every row.

## Implementation

Introduce a `LedgerFilingSnapshot` typed record: an ordered set of
`(transaction_id, row_fingerprint)` pairs over the revision's contributors plus a
`snapshot_fingerprint` (SHA-256 over the sorted pairs) and a `captured_at`. The
`row_fingerprint` hashes the tax-relevant projection of a transaction
(id, dates, signed amount, currency, direction, business_classification,
business_pct, taxable_base, iva_rate, iva_amount, iva_category, category_id,
irpf_category, counterparty_eu_member_state, fx_rate, value_in_eur,
lifecycle_state). The snapshot is computed from the revision's
`source_transaction_ids` against the live catalogue at the moment a revision
transitions to `VERIFICADO_COMPLETO` (and re-affirmed/recaptured at `PRESENTADO`),
and stored on the `CalculationRevision` as an optional
`ledger_filing_snapshot` field (default `None` for legacy revisions). Because it
derives from `source_transaction_ids`, a non-ledger modelo yields a snapshot over
the empty set -- a valid, uniform, trivially-stable record. A pure
`evaluate_ledger_filing_staleness(revision, live_catalogue)` recomputes the
current fingerprint and classifies each contributor as unchanged / changed /
removed, returning a staleness verdict. A new `BucketEventType`
(`MODELO_LEDGER_DEPENDENT_STAMPED_STALE`, mirroring the censo pattern) and a
work-unit stale marker surface drift through `status` / `verify` / `check`. The
existing block stays as the write-time defense; the snapshot is the audit +
staleness layer. Amendments persist both the superseded filing's snapshot and the
new one so a complementaria/sustitutiva can diff the ledger deltas it corrects.

## Rationale

Integrity-through-blocking is necessary but insufficient: it leaves no
point-in-time record, no tamper-evidence, and no staleness signal, and it does
not cover non-ledger modelos. Content-addressed snapshot backing makes every
filing self-certifying ("this return was computed from ledger state X"),
detectable-when-drifted, and uniform across the whole modelo surface, at bounded
storage cost. It is the filing-time counterpart to the registry's existing
snapshot discipline (`RegistrySnapshot`) applied to the ledger side of the
calculation.

## Consequences

- Gains: auditable, reconstructable filing provenance for every modelo;
  tamper-evidence independent of the block; a real staleness signal that drives
  recompute prompts; a basis for amendment diffs.
- Costs: a new persisted field on the revision and a new event type; the
  capture/compare paths must be covered by strict roundtrip + anti-tautology
  tests; care needed so the snapshot does not perturb the revision-id hash.
- Pitfalls: the row-fingerprint projection must include exactly the facts that
  affect a casilla (no more, no less) or staleness will false-positive on
  cosmetic edits or false-negative on material ones; the empty-set snapshot for
  non-ledger modelos must be explicitly tested so uniformity is real, not assumed.

## Codification candidates

- **Rule slug:** `modelo-filings-are-ledger-snapshot-backed`.
  **Rule:** Every modelo calculation revision that reaches a verified or filed
  state MUST carry an immutable, content-addressed ledger snapshot (a fingerprint
  over its contributing transactions' tax-relevant facts), and any divergence
  between the live ledger and a filed snapshot MUST surface as an explicit
  staleness signal -- uniformly for every modelo, ledger-fed or not.
