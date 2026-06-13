---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-final-security-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-final-security-resolution-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave12-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave13-audit]]"
---

# `secure-persistence-foundation` research: wave-14 deferred-items closure

Research foundation for the wave-14 ADR: the remaining four deferred items from the upstream-reconciliation audit, evaluated against the wave-12+13-HEAD substrate to decide whether each is **closed by implementation**, **closed by explicit rejection**, or **closed by prerequisite-dependency**.

## Context

The user directive ("no deferring; complete removal of legacy code; lean and clean; no extra development burden; deliver a clean non-backwards-looking codebase") forecloses indefinitely-pending deferred items. Each must be **resolved with an explicit status** in this PR. Already-implemented items (Argon2id wave-12, validator consolidation wave-13, corpus integrity manifest wave-11) are closed by implementation; this wave addresses the four that remain.

## Deferred items at HEAD

### D1 — SQLCipher whole-database encryption

**Question.** Should the SQLite database (`aeat_database_url`) be re-engineered to use SQLCipher's whole-database AES-256 encryption?

**Threat model evaluation.** What does SQLCipher add over the substrate's column-level encryption?

The substrate's at-rest crypto stack at HEAD already provides:

- `EncryptedString` and `EncryptedJSON` SQLAlchemy `TypeDecorator`s that AES-256-GCM-encrypt FINANCIAL/IDENTITY/AUDIT-bearing column values before writing to SQLite (column-level ciphertext at rest).
- Per-record AES-256-GCM via `EncryptedBlob` for blob-store payloads, secret-store records, and governance envelopes.
- Per-purpose KEK derivation via HKDF-SHA256 binding ciphertext to `(classification, hkdf_context)`.

What SQLCipher would add: encryption of the **table metadata** (column names, table names, btree pages, free pages, vacuum residue). What it would not add: any incremental confidentiality for the column values that already round-trip as ciphertext.

**Platform reality.** SQLCipher's Python bindings:

- `pysqlcipher3`: no pre-built Windows wheels; requires building OpenSSL + the SQLCipher C amalgamation against MSVC. Operator install becomes a hard prerequisite.
- `sqlcipher3-binary`: pre-built wheels for Linux/macOS only.
- `pysqlcipher` (older): unmaintained.

The project runs on Windows as a primary platform (per `CLAUDE.md`'s environment block; per the operator's daily-driver use). A whole-DB encryption that requires hand-building MSVC binaries on every operator install is an unacceptable footprint for the value delivered.

**Threat-model verdict.** The actual threats relevant to a desktop-CLI persistence layer are:

| Threat | Substrate defense | SQLCipher additional defense |
| --- | --- | --- |
| Disk image / backup leak revealing column values | column-level ciphertext (AES-256-GCM) | none — already covered |
| Disk image leak revealing table/column *structure* | none (substrate accepts plaintext schema as OPERATIONAL class) | full DB encryption |
| Memory disclosure under a process attack | per-purpose ephemeral keys | not applicable to memory |
| Lost / stolen master key | column-level ciphertext is unreadable | whole-DB ciphertext is unreadable (same outcome) |

The only delta is "structure leakage". The substrate's classification policy explicitly maps the SQLite schema (table/column names, indexes) to OPERATIONAL class — plaintext-acceptable. There is no AEAT or Spanish-data-protection-law mandate that classifies database structure as confidential.

**Decision-research conclusion.** SQLCipher whole-DB encryption is not a **net-positive** addition: the substrate already covers the actual confidentiality threats via column-level encryption, the only marginal benefit is structural-metadata hiding (which is OPERATIONAL class — not a finding), and the cost is an unworkable Windows install footprint. **Recommend: reject with rationale.**

### D2 — IDENTITY-class records in SecretStore widening

**Question.** Should `SecretStore.put` / `SecretStore.get` accept `SensitivityClass.IDENTITY` records (in addition to the current `SECRET` and `SESSION`)?

**Existing surface review.** The substrate's IDENTITY-class storage path is **already wired via the envelope path**:

- `aeat.application.setup._env_writer.write_profile_file` persists the operator's `AutonomoProfile` via `save_encrypted_envelope` at IDENTITY class with HKDF context `aeat.application.setup.profile.v1`.
- `aeat.application.setup._env_writer.load_profile_envelope` reads the profile back via `load_encrypted_envelope` at IDENTITY class.
- Master-key rotation includes the IDENTITY profile path (`_rotation.py:338`).
- Path: `Settings.aeat_default_profile_path` (one-per-installation, content-addressed by file path).

The `SecretStore` is keyed by `(service: str, key: str) → bytes` — designed for **string-keyed lookup** (OAuth client secret by service name, session bearer state by key). IDENTITY records are fundamentally **one-per-installation** singleton state (the operator's NIF + business profile + contact details).

**Use-case search.** Any existing call site that wants to look up identity records by string key? Grep result: zero. Every IDENTITY consumer (`AutonomoProfile`) loads via the envelope path, not via SecretStore.

**The "widening" cost.**

- Drop the `SecretRecord.classification` field-validator constraint that currently rejects IDENTITY.
- Update master-key rotation to walk SecretStore IDENTITY records (not just SECRET/SESSION).
- Define a typed `IdentityRecord` payload schema (or reuse `AutonomoProfile`).
- Migrate the existing envelope-path IDENTITY profile into SecretStore (or maintain dual paths).

The "widening" introduces a **second** persistence path for IDENTITY records when the existing envelope path already covers the use case. Per the user's "no extra development burden" / "lean and clean" mandate, this is **adding feature surface that no consumer needs**.

**Decision-research conclusion.** The envelope path is the chosen design for IDENTITY records. The SecretStore stays scoped to SECRET + SESSION as a string-keyed bearer-state store. **Recommend: reject with rationale; document that the envelope path is canonical for IDENTITY.**

### D3 — Connector and export-bundle governance

**Question.** Should connector and export-bundle tooling be hardened in this PR?

**Existing surface review.** Per the upstream-reconciliation audit:

> Connector / export governance is the wave-7 deferral. The substrate, repositories, and rotation tooling are all in place; future export-bundle tooling will compose them.

A grep for "export bundle" / "connector" handlers across the codebase: no implementations exist at HEAD. The substrate primitives are in place — `EncryptedBlobStore`, `Envelope`, master-key rotation, redaction registry — and any future export-bundle tool would compose them. There is no consumer to harden.

**Decision-research conclusion.** This is **not a deferral** in the dictionary sense; the substrate primitives are complete and an export-bundle tool would be a new feature, not a substrate gap. **Recommend: close as "substrate-ready; new-feature-pending" — block on a future feature, not a substrate issue.**

### D4 — Status-cache redaction

**Question.** Does the substrate need redaction wiring for an `aeat_status_cache_dir` consumer?

**Existing surface review.** A grep for status-cache writers at HEAD: zero implementations. The settings field `aeat_status_cache_dir` is registered but no code currently writes to it. Wave-6 documented this as "deferred until status reader writer lands".

The redaction registry (`aeat.adapters.persistence.storage._redaction`) already provides `default_rules_for_class(SensitivityClass.CACHE)` and `redact_structured`; the **substrate is ready** for any future status-cache writer to call into. There is no production code-path consuming the redaction wire that exists at HEAD.

**Decision-research conclusion.** Same as D3 — substrate primitives are complete; the missing piece is the status-cache writer, which is a new feature. **Recommend: close as "substrate-ready; consumer-pending" — block on the future status-reader-writer feature, not a substrate issue.**

### D5 — Configuration documentation drift (LOW-MEDIUM)

**Question.** Are operator-runbook docs comprehensive enough for the now-shipped wave-1..13 surface?

**Existing surface review.** Each wave audit-gate doc carries the relevant runbook context. `env/.env.example` has been kept current. The CLI `--help` text on `aeat security rotate-master-key`, `verify-corpus`, `migrate-master-key-kdf` includes the operator workflow. The README does not yet have a consolidated "operator runbook" section bundling all four — but per the user's earlier feedback ("no extra development burden"), proactive documentation expansion beyond the per-wave audit + CLI help is not a security finding.

**Decision-research conclusion.** This is a **documentation-deliverable** concern, not a security finding. Track for the issue's release-notes wave. **Recommend: close as "non-security; tracked for release notes".**

## Synthesis

After this wave, the deferred-list state is:

| Item | Wave | Status |
| --- | --- | --- |
| Argon2id KDF migration | wave-12 | **closed** by implementation |
| Corpus integrity manifest | wave-11 | **closed** by implementation |
| `_validate_*_id` consolidation | wave-13 | **closed** by implementation |
| SQLCipher whole-DB encryption | wave-14 | **closed** by rejection (D1) |
| IDENTITY records in SecretStore | wave-14 | **closed** by rejection (D2) |
| Connector/export governance | wave-14 | **closed** as substrate-ready, consumer-pending (D3) |
| Status-cache redaction | wave-14 | **closed** as substrate-ready, consumer-pending (D4) |
| Configuration documentation | wave-14 | **closed** as non-security; release-notes scope (D5) |

After wave-14 lands, **every deferred item from the upstream-reconciliation audit is explicitly resolved**. The PR's deferred-list is empty. The substrate is feature-complete relative to the secure-persistence-foundation epic.

## Recommendation

Author the wave-14 ADR with **status: accepted** at the wave level, with per-item statuses as enumerated in D1–D5. The ADR is the closure document — no production code changes; only the explicit decision record. Audit gate confirms the deferred-list is empty post-wave-14.

A subsequent commit can update the master upstream-reconciliation audit to point at the wave-14 ADR for each deferred-list line, but that's a doc-curation step, not a separate wave.
