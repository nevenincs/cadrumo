---
name: aeat-ledger-contract
trigger: always_on
---

# AEAT ledger contract: amounts, evidence, advisories, derived indexes

## Amount is an absolute magnitude; direction is the sole flow authority

A ledger transaction stores a **non-negative** `amount`; flow direction is
carried solely by the `direction` enum (INCOMING / OUTGOING /
INTERNAL_TRANSFER). No model, adapter, evidence row or CLI surface may encode
flow in the sign of an amount. The constraint is enforced at the `RawTransaction`
boundary so import and manual paths are both gated, and evidence rows mirror the
absolute convention. There is no signed-amount shape to read, migrate or bridge.

Flow was once encoded twice and the two could disagree; consistency was enforced
only on the manual command, so the import path derived direction from the sign
and a zero-amount import silently classified as INCOMING.

## Evidence is encrypted bytes, and rides with the revision that used it

Every ledger evidence record must carry the document's **encrypted bytes** in a
bucket-scoped secure-object namespace. A Gmail, Drive or URL reference must be
fetched and encrypted, or the attachment refused — never stored as a link-only
manifest. A stored pointer is not evidence: links rot, permissions change, and a
later audit cannot answer why a casilla had a value from a dead manifest.

Every modelo calculation revision that derives any casilla from the ledger MUST
bundle the typed ledger evidence — contributing-transaction projections plus
manual fact-basis entries — pegged to the revision's snapshot fingerprint, and
every export MUST carry that evidence or a resolvable in-system reference. An
export carrying neither is refused. Revision state once stored only fingerprints,
so the fact basis explaining *why a casilla holds its value* was absent from the
persisted revision and every export.

## The IVA advisory fires only on cuota-bearing categories

The unconsumed-declarable-IVA advisory MUST fire only on `IvaCategory` values
legally expected to produce a cuota a binding should route. Categories that are
**cuota-less by law** (exempt, zero-rated, not-subject, exempt intra-community
supply, triangulation, other-regime) MUST be excluded via the named
`CUOTA_LESS_M303_IVA_CATEGORIES` frozenset — never an inline literal.

The advisory once false-fired on categories bearing no cuota by law, which
legitimately match no cuota binding — noise that trains operators to ignore the
alert. It only earns trust if every fire is a genuine unrouted cuota.

## The participation index is derived and rebuildable

The transaction-to-revision participation index is a **derived encrypted cache**,
co-written atomically with revision persistence and rebuildable from the revision
catalogue. Lifecycle correctness MUST rely on the live catalogue scan, never on
index freshness — if deletion guards depended on the cache, a stale write could
silently permit destructive ledger changes.

## How

- **Good:** `RawTransaction.amount` carries a non-negative validator firing for
  both import adapters and the manual command, locked by a save-load-equality
  roundtrip plus an anti-tautology proof (corrupt the on-disk amount negative,
  assert load refusal). Import adapters map the export sign or debit/credit
  signal to a direction at the parse boundary, store the absolute amount, and
  refuse a zero-amount source row.
- **Good:** the doc-link path resolves a permitted file to bytes, stores them
  through the attachment secure-object namespaces, and records source metadata;
  out-of-scope references fail with an actionable refusal naming the scope
  upgrade or manual-download path.
- **Good:** the evidence projection resolves source transaction ids into typed
  rows bound to the fingerprint, persisted inside the encrypted revision and
  surviving a strict roundtrip with every defaultable field populated
  non-default; a coverage assertion makes a bundle that drops a resolved
  contributor raise.
- **Good:** verification or filing persistence co-emits participation entries in
  the same secure-object write batch as the revision state change, and a rebuild
  action regenerates them from finalized catalogues.
- **Bad:** writing a negative amount to encode an expense, or a
  `direction_from_amount` helper reading `amount < 0` downstream of the parse
  boundary.
- **Bad:** persisting only a URL as evidence, or falling back to link storage
  after a fetch permission error.
- **Bad:** flagging an exempt entrega intracomunitaria or an export as "unrouted
  declarable IVA"; or silencing a genuine unrouted reverse-charge cuota by adding
  it to the cuota-less set.
- **Bad:** allowing a ledger transaction delete because the participation index
  has no entry for it; or writing a plaintext index outside the encrypted
  repository.

Source: ADRs `2026-06-10-ledger-amount-direction-adr`,
`2026-06-10-ledger-evidence-enforcement-adr`,
`2026-06-03-modelo-export-evidence-parity-adr`,
`2026-06-09-modelo-iva-routing-carry-adr`,
`2026-06-10-ledger-modelo-crossref-adr`.
