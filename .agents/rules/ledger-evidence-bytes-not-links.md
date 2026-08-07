---
name: ledger-evidence-bytes-not-links
trigger: always_on
---

# Ledger evidence: encrypted bytes, and bundled with the revision that used them

## Bytes, never links

Every ledger evidence record must carry the document's **encrypted bytes** in a
bucket-scoped secure-object namespace. A Gmail, Drive, or URL reference must be
fetched and encrypted, or the attachment must be refused — never stored as a
link-only manifest.

A stored pointer is not evidence: links rot, permissions change, and a later
modelo audit cannot answer why a casilla had a value from a dead `text/uri-list`
manifest.

## How

- **Good:** the doc-link path resolves a permitted file to bytes, stores them
  through the attachment secure-object namespaces, and records source metadata in
  the manifest. Out-of-scope references fail with an actionable refusal naming
  the scope upgrade or the manual-download path.
- **Bad:** persisting only a URL as evidence, or falling back to link storage
  after a fetch permission error.

## Ledger-derived revisions bundle their evidence

Every modelo calculation revision that derives any casilla from the ledger MUST
bundle the typed ledger evidence — the contributing-transaction projections plus
the manual fact-basis entries — pegged to the revision's snapshot fingerprint.
Every export of such a revision MUST carry that evidence, or a resolvable
in-system reference to it; an export carrying neither is refused.

Revision state once stored only fingerprints, so the fact basis explaining *why a
casilla holds its value* was absent from the persisted revision and every export.
A human files outside the app, and unre-derivable numbers cannot be defended.

## How

- **Good:** the evidence projection resolves source transaction ids into typed
  evidence rows plus manual fact-basis entries bound to the fingerprint, captured
  in one catalogue load, persisted inside the encrypted revision, and surviving a
  strict save-load-equality roundtrip with every defaultable field populated
  non-default. A coverage assertion makes a bundle that drops a contributor
  present in the resolved ids raise. Offline and online exports read the same
  evidence to render an identical surface.
- **Bad:** persisting a ledger-derived revision with only the fingerprint;
  letting an export proceed with neither bundled evidence nor a resolvable
  reference; or asserting the roundtrip against numbers hand-computed from the
  same formula.

Source: ADRs `2026-06-10-ledger-evidence-enforcement-adr`,
`2026-06-03-modelo-export-evidence-parity-adr`. Companions:
`sensitive-financial-data-secure-storage-only`, `aeat-roundtrip-discipline`.
