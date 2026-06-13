---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-27-security-storage-audit-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-final-security-resolution-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave7-audit]]"
---



# `secure-persistence-foundation` upstream-audit reconciliation | (**status:** `closed`)

## Purpose

The 2026-04-27 storage security audit was the trigger for the
`secure-persistence-foundation` feature cluster. Across 10 waves +
the final security audit + the audit-resolution commit, every
finding from that upstream document has been addressed. This
reconciliation document maps each upstream finding to the commit
or wave that closed it, so a future reviewer can confirm closure
without re-reading 10 wave audit-gate reports.

## Findings × resolution

### CRITICAL: plaintext repo-local secret and credential persistence

Closed by **Wave 2** (commits up to `1690039`). Operator credentials
- OAuth client secrets, service-account private keys, OAuth refresh
tokens, MCP credentials, operator-profile records - all migrated
to the `aeat.adapters.persistence.storage.SecretStore` ciphertext-at-rest substrate via
the per-consumer adapters in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_secret_adapters.py`.
The `aeat secrets` CLI (`aeat secrets list/put/rm/rotate`) provides
the operator-facing surface.

### CRITICAL: broad plaintext persistence of sensitive financial / identity / session-adjacent business records

Closed across **Waves 3 - 10 + final security audit**. Every
governance repository now writes AES-256-GCM ciphertext at rest:

- `TransactionCatalogueRepository` (FINANCIAL) - Wave 3 + Wave 7 +
  Final Audit LEAK-001.
- `FilingDraftRepository` (FINANCIAL) - Wave 4.
- `FilingAmendmentRepository` (AUDIT) - Wave 4.
- `FilingHistoryRepository` (AUDIT) - Wave 4.
- `JustificanteRepository` (AUDIT) - Wave 4.
- `SubmissionRepository` (AUDIT) - Wave 4.
- `InvoiceCatalogueRepository` (FINANCIAL) - Final Audit LEAK-002.
- `EncryptedAttachment manifest` (FINANCIAL) - Final Audit LEAK-003.
- `UsageRatioProfile` (FINANCIAL) - Final Audit USAGE-001.
- `JsonFileDivergenceRepository` (AUDIT) - Final Audit LEAK-005.
- `WorkflowResult` envelopes (AUDIT) - Wave 8.
- `AutonomoProfile` (IDENTITY) - Final Audit LEAK-004.
- `RunTrace` + `RunEvent` redacted (DIAGNOSTIC) - Wave 5 +
  Final Audit TRACE-001.
- LLM cache + usage redaction (DIAGNOSTIC) - Wave 6.

AAD binding on every cipher envelope authenticates
`(classification, hkdf_context)` so cross-consumer ciphertext
substitution and class relabel both fail with `DecryptionError`.

### HIGH: audit / log / debug artifacts outside controlled roots

Closed by upstream PR #432 (live-submit permanently forbidden) +
the merge in Wave 9. With live submission excised, the legacy
`.aeat/live-submit-audit.log` writer no longer has a use case;
both the legacy writer and the wave-4 phase-5 governed audit sink
were removed. The remaining run-trace / browser-trace / debug
artefacts now live under `aeat_runs_dir` /
`aeat_status_browser_trace_dir` etc., all of which are normalised
by `_normalize_repo_relative_paths` (no path drift).

### HIGH: profile and config CLI surfaces write identity and financial profile state plaintext

Closed by **Wave 2** (auth-config secret-store consumer migrations)
+ **Wave 8** (CLI silent-leaker close) + **Final Audit LEAK-004**
(setup wizard `AutonomoProfile` writer). Every profile / config
write that handles identity-bearing data now routes through the
ciphertext substrate.

### MEDIUM-HIGH: path-governance drift weakens containment guarantees

Closed - the upstream audit cited
`aeat_invoices_dir`, `aeat_attachments_dir`, and `aeat_runs_dir`
as omitted from `_normalize_repo_relative_paths` in
`src/aeat/config.py`. Inspection at HEAD confirms all three
(plus `aeat_workflow_runs_dir`, the new `aeat_audit_dir`, the
new `aeat_secret_store_dir`, `aeat_blob_store_dir`,
`aeat_sync_divergence_file_dir`, `aeat_filing_history_dir`,
`aeat_justificantes_dir`, etc.) are now in the validator's field
list. No path drift remains.

### MEDIUM: schema and version evolution fragmented by domain

**Partially closed.** The substrate's `Envelope[PayloadT]` carries
a per-record `schema_version` integer + an `EnvelopeMigrator`
Protocol so per-domain repositories can declare forward migrators.
Every wave-4-and-later repository pins a `_*_ENVELOPE_VERSION`
constant. Domains still outside the envelope substrate (declaracion
parsers, ruleset evolution, schema cache) remain on per-domain
versioning - this is by design and outside the
`secure-persistence-foundation` scope; the feature establishes the
contract, individual domains opt in over time.

### MEDIUM: connector and export surfaces allow uncontrolled local writes

**Out of scope - flagged for future wave.** Connector / export
governance is the wave-7 deferral (per the wave-4 ADR's "Out of
scope"). The substrate, repositories, and rotation tooling are
all in place; future export-bundle tooling will compose them.

### LOW-MEDIUM: configuration documentation drift

**Partially closed.** Several wave audit-gate docs include the
relevant settings; `env/.env.example` has been kept current.
Comprehensive operator-runbook documentation (e.g. master-key
rotation walkthrough, migration helper usage) is a documentation
deliverable for the issue's release-notes wave, not a security
finding per se.

## Final-audit additions (not in the upstream audit)

The internal final security audit at HEAD identified four HIGH and
four MEDIUM findings that were not visible to the upstream
2026-04-27 audit (the upstream audit ran against a smaller persistence
surface). All eight have been closed - see
`2026-04-30-secure-persistence-foundation-final-security-resolution-audit.md`
for the per-finding closure log.

## Items intentionally deferred

Recorded so future waves can pick them up; these are NOT regressions
nor open security findings - they are scope decisions:

- **Argon2id KDF migration**. The current substrate uses scrypt
  (N=2^17, r=8, p=1) for password-derived keys via
  `FileFallbackMasterKeyProvider`. Argon2id is the modern
  recommendation but adds a new runtime dependency
  (`argon2-cffi`). Deferred pending operator-approval of the new
  dep.
- **SQLCipher migration**. The SQLite database used by the wave-1
  ORM substrate is plaintext at rest; column-level encryption via
  `EncryptedString` / `EncryptedJSON` covers the identity-bearing
  fields. Whole-database encryption via SQLCipher requires a new
  dep + a custom SQLAlchemy dialect. Deferred.
- **IDENTITY-class records in the secret store widening**. The
  current SecretStore is keyed by `(service, key)` and stores
  generic byte payloads. A typed IDENTITY-class record schema
  (NIF + business profile + contact details) would be a separate
  ADR.
- **Status-cache redaction**. `aeat_status_cache_dir` is
  registered but has no current writer. Will revisit when an
  AEAT status reader lands.
- **Corpus integrity directory-level manifest**. Per-record
  SHA-256 already exists for manuals + casillas; a top-level
  directory manifest is a future deliverable.
- **`_validate_*_id` consolidation**. Each repository has its own
  near-identical id validator. Pure code-quality refactor; no
  security impact.

## Decision

All HIGH / CRITICAL findings from the upstream 2026-04-27 audit are
closed at HEAD. The substrate, the per-domain repositories, the
master-key rotation tool, and the redaction discipline are all
verifiably in place with leak-canary regression tests.

Two MEDIUM findings (schema/version evolution; connector/export
governance) are partially closed within the scope of the
`secure-persistence-foundation` feature; both are explicitly
flagged for follow-on waves rather than rolled into this PR.

The internal final security audit + resolution log closes a further
4 HIGH + 4 MEDIUM findings the upstream document did not surface.

The PR is ready for fresh external code review.
