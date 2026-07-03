---
name: ledger-evidence-bytes-not-links
---

# Ledger evidence bytes, not links

## Rule

Every ledger evidence record must carry the document's encrypted bytes in a bucket-scoped secure-object namespace; a Gmail, Drive, or URL reference must be fetched and encrypted or the attachment must be refused, never stored as a link-only manifest.

## Why

The `2026-06-10-ledger-evidence-enforcement-adr` made encrypted evidence bytes the C2 ledger evidence invariant. A stored pointer is not evidence: links rot, permissions change, and a later modelo audit cannot answer why a casilla had a value from a dead `text/uri-list` manifest. This rule is the evidence-specific companion to `sensitive-financial-data-secure-storage-only`.

## How

- Good: `doclink` resolves a permitted Drive file to bytes, stores the bytes through the attachment secure-object namespaces, and records source metadata in the manifest.
- Good: Gmail links, arbitrary URLs, and out-of-scope Drive files fail with an actionable refusal that names the scope-upgrade or manual-download path.
- Bad: persisting only `https://...`, a Gmail message URL, or a Drive URL as `text/uri-list` and treating it as evidence.
- Bad: falling back to link storage after a fetch permission error.
