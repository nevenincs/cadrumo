---
name: sensitive-financial-data-secure-storage-only
trigger: always_on
---

# Sensitive financial data persists only in secure storage

## Rule

All sensitive financial data — every purchase invoice and every incoming or
outgoing business invoice, every bank statement and supporting document, and any
decrypted evidence bytes derived from them — persists ONLY inside the encrypted
secure-storage backend, accessed through the runtime wrapper that maps to the
active profile bucket (`secure_object_repository_for_active_bucket` /
`secure_object_repository_for_bucket`, the `SecureObjectRepository` substrate, and
the content-addressed `AttachmentStore` that wraps it). No code path may write or
persist sensitive financial data anywhere outside secure storage: no temp files, no
scratch directories, no plaintext side stores, no caches on disk, no logs. Decrypted
bytes may exist only transiently in process memory and must never be written out. A
path pointer to a cleartext file on operator disk (e.g. a `source_path` field) is
NOT a valid persistent home for invoice bytes; the bytes themselves belong in secure
storage.

## Why

This invariant is enforced by prior ADRs and by secure-storage enrollment across
multiple epic runs; it is the load-bearing confidentiality guarantee of the whole
application. The `llm-evidence-classification` Stage-3 research/ADR pass on
2026-06-10 is the worked example of how an agent breaks it: an early draft, reaching
for "let an LLM read the invoice", designed a decrypted-temp-file route for the
subprocess CLI agents and framed "which providers may receive decrypted evidence" as
a tunable privacy boundary. The operator rejected this outright — taking sensitive
financial data out of secure storage (to a temp file, or by uploading it off-host)
is never acceptable, and is categorically unacceptable for gestors or any serious
professional usage. Writing a client's invoice bytes to a scratch file or shipping
them to a third party is exactly the exposure secure storage exists to prevent. The
rule is restated in the rule layer (not only in ADRs) because this is the authoring
moment where the temptation appears, and a rule is what loads into the next agent's
context before it writes the violating line.

## How

- **Good:** invoice/attachment bytes are written and read through the
  content-addressed `AttachmentStore` (`put_bytes` / `read_bytes`), which wraps
  encrypted `Envelope` records in `SecureObjectRepository` at `FINANCIAL`
  sensitivity via the active-bucket runtime wrapper. A consumer that needs the bytes
  (e.g. to hand a document to an on-host model) reads them into memory and uses them
  transiently; nothing is written to disk.
- **Good:** a feature that must let a model read a document runs the reader on-host
  (in-tree text extraction, or a local vision model fed in-memory base64) so the
  bytes never leave the machine. Any off-host transmission is gated behind an
  explicit, per-invocation, default-off, gestor-barred operator consent
  acknowledgement (see `off-host-evidence-upload-requires-explicit-consent-gate` when
  it lands) and never uses a transport that writes a file.
- **Bad:** materialising decrypted evidence to a temp file (even "bounded
  lifetime", even `chmod 600`, even "removed promptly") so a subprocess CLI tool can
  read it by path. The temp file is persistence outside secure storage — forbidden.
- **Bad:** storing only a `source_path` to a cleartext file on operator disk and
  treating that as the durable home of the bytes. The bytes must be in secure
  storage; a path is not storage.
- **Bad:** writing sensitive financial values to logs, a plaintext JSON side store,
  an on-disk cache, or a scratch directory for debugging.

## Source

Operator directive recorded 2026-06-10 during the `llm-evidence-classification`
Stage-3 research/ADR pass on the `chore/eliminate-shims` branch, after an ADR draft
proposed a decrypted-temp-file evidence-reading route. Backing decision: ADR
`2026-06-10-llm-evidence-classification-adr` (the `sensitive-financial-data-persists-
only-in-secure-storage` and `off-host-evidence-upload-requires-explicit-consent-gate`
codification candidates). Companion rules: `aeat-safety-legal-gates`,
`aeat-architecture-boundaries`.
