---
name: sensitive-financial-data-secure-storage-only
---

# Sensitive financial data persists only in secure storage

## Rule

All sensitive financial data — every purchase invoice and every incoming or
outgoing business invoice, every bank statement and supporting document, and any
decrypted evidence bytes derived from them — persists ONLY inside the encrypted
secure-storage backend, accessed through the active-profile-bucket runtime
wrapper (`secure_object_repository_for_active_bucket` /
`secure_object_repository_for_bucket`, the `SecureObjectRepository` substrate,
and the content-addressed `AttachmentStore` that wraps it). No code path may
write or persist sensitive financial data anywhere outside secure storage: no
temp files, no scratch directories, no plaintext side stores, no on-disk caches,
no logs. Decrypted bytes may exist only transiently in process memory and must
never be written out. A path pointer to a cleartext file on operator disk (e.g. a
`source_path` field) is NOT a valid persistent home for invoice bytes; the bytes
themselves belong in secure storage.

## Why

This is the load-bearing confidentiality guarantee of the whole application. The
`llm-evidence-classification` Stage-3 pass (ADR
`2026-06-10-llm-evidence-classification-adr`) is the worked failure: an early
draft designed a decrypted-temp-file route for subprocess CLI agents and framed
off-host upload as a tunable boundary; the operator rejected it outright —
removing sensitive financial data from secure storage (temp file or off-host) is
never acceptable, and categorically unacceptable for gestors or serious
professional use.

## How

- **Good:** invoice/attachment bytes are written and read through the
  content-addressed `AttachmentStore` (`put_bytes` / `read_bytes`), wrapping
  encrypted `Envelope` records in `SecureObjectRepository` at `FINANCIAL`
  sensitivity via the active-bucket wrapper; a consumer reads them into memory
  and uses them transiently, writing nothing to disk. A model that must read a
  document runs on-host (in-tree extraction or a local vision model fed in-memory
  base64); any off-host transmission is gated behind an explicit, per-invocation,
  default-off, gestor-barred consent acknowledgement (see
  `off-host-evidence-upload-requires-explicit-consent-gate` when it lands) and
  never uses a file-writing transport.
- **Bad:** materialising decrypted evidence to a temp file (even bounded-lifetime,
  `chmod 600`, promptly removed) for a subprocess to read by path; storing only a
  `source_path` to a cleartext file as the durable home; or writing sensitive
  values to logs, a plaintext JSON side store, an on-disk cache, or a scratch dir.

## Source

Operator directive recorded 2026-06-10; ADR
`2026-06-10-llm-evidence-classification-adr`. Companion:
`aeat-safety-legal-gates`, `aeat-architecture-boundaries`.
