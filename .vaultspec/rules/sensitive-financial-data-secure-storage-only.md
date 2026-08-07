# Sensitive financial data persists only in secure storage

All sensitive financial data — every purchase invoice, every incoming or outgoing
business invoice, every bank statement and supporting document, and any decrypted
evidence bytes derived from them — persists ONLY inside the encrypted
secure-storage backend, accessed through the active-profile-bucket runtime
wrapper (`secure_object_repository_for_active_bucket` /
`secure_object_repository_for_bucket`, the `SecureObjectRepository` substrate,
and the content-addressed `AttachmentStore` that wraps it).

No code path may write or persist sensitive financial data anywhere else: no temp
files, no scratch directories, no plaintext side stores, no on-disk caches, no
logs. **Decrypted bytes may exist only transiently in process memory and must
never be written out.** A path pointer to a cleartext file on operator disk is
NOT a valid persistent home; the bytes themselves belong in secure storage.

This is the load-bearing confidentiality guarantee of the whole application. An
early design proposed a decrypted-temp-file route for subprocess agents and
framed off-host upload as a tunable boundary; the operator rejected it outright —
removing sensitive financial data from secure storage, by temp file or off-host,
is never acceptable, and categorically unacceptable for gestors or serious
professional use.

## How

- **Good:** invoice and attachment bytes are written and read through the
  content-addressed `AttachmentStore`, wrapping encrypted `Envelope` records at
  `FINANCIAL` sensitivity via the active-bucket wrapper; a consumer reads them
  into memory and writes nothing to disk. A model that must read a document runs
  **on-host** (in-tree extraction or a local vision model fed in-memory base64);
  any off-host transmission is gated behind an explicit, per-invocation,
  default-off, gestor-barred consent acknowledgement, and never uses a
  file-writing transport.
- **Bad:** materialising decrypted evidence to a temp file — even
  bounded-lifetime, mode 600, promptly removed — for a subprocess to read by
  path; storing only a `source_path` to a cleartext file as the durable home; or
  writing sensitive values to logs, a plaintext side store, an on-disk cache, or
  a scratch dir.

Source: operator directive; ADR `2026-06-10-llm-evidence-classification-adr`.
Companions: `aeat-safety-legal-gates`, `ledger-evidence-bytes-not-links`.
