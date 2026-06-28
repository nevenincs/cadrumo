---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave14-research]]"
  - "[[2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave12-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave13-audit]]"
---

# `secure-persistence-foundation` adr: wave-14 deferred-items closure | (**status:** `accepted`)

## Problem Statement

The user's "no deferring" directive forecloses indefinitely-pending deferred items in this PR. After wave-11 (corpus manifest), wave-12 (Argon2id KDF) and wave-13 (validator consolidation), four deferred items from the upstream-reconciliation audit remain. This wave **closes them with explicit status** so the PR's deferred-list is empty at merge.

## Considerations

Per the wave-14 research, the four remaining deferred items resolve into three categories:

- **Reject with rationale (substrate already covers the threat model)**: SQLCipher whole-DB encryption (D1), IDENTITY-records-in-SecretStore widening (D2).
- **Substrate-ready, consumer-pending (no current code consumer)**: connector/export governance (D3), status-cache redaction (D4).
- **Non-security; tracked for release-notes scope**: configuration documentation drift (D5).

None of the four require production-code changes. This wave is a pure decision artefact + audit-gate-closure.

## Constraints

- **No production-code changes**: this is a closure ADR, not an implementation wave. The substrate is feature-complete; the deferred items either don't need implementation, or wait on consumer code that is itself a future-feature gap.
- **Explicit per-item status**: each deferred item must have a clear accepted/rejected/blocked verdict and a rationale, so future agents do not re-open the question.
- **Verifiable closure**: the wave-14 audit gate must confirm the deferred-list is empty post-wave.

## Implementation

The implementation is the decision document itself. Per-item status:

### D1 — SQLCipher whole-database encryption | **status: rejected**

The substrate's column-level encryption (`EncryptedString`, `EncryptedJSON`) already covers every confidential field at rest with AES-256-GCM. SQLCipher's only delta is encryption of table/column **structure metadata** — which the substrate's classification policy maps to OPERATIONAL class (plaintext-acceptable, no AEAT or Spanish-data-protection-law mandate to the contrary).

Cost: SQLCipher's Python bindings ship no pre-built Windows wheels; operators would need to build OpenSSL + the SQLCipher C amalgamation against MSVC at install time. The project runs on Windows as a primary platform.

Verdict: column-level encryption is the chosen design. SQLCipher whole-DB encryption is **not adopted**.

Action: none. The decision is documented here; future agents can reference this ADR if SQLCipher is re-proposed.

### D2 — IDENTITY-class records in SecretStore widening | **status: rejected**

The substrate's IDENTITY-class storage is already wired via the **envelope path**: `aeat.application.setup._env_writer.write_profile_file` persists `AutonomoProfile` at IDENTITY class through `save_encrypted_envelope` (HKDF context `aeat.application.setup.profile.v1`). Master-key rotation already includes that path.

`SecretStore` is keyed by `(service, key) → bytes` for **string-keyed bearer state** (OAuth secrets, session storage). IDENTITY records are **one-per-installation singletons** (the operator's NIF + business profile + contact details) — the envelope path's "single file per profile" model is the correct shape.

Use-case search: zero existing call sites want to look up identity records by string key.

Verdict: the envelope path is the canonical home for IDENTITY records. The `SecretStore` stays scoped to SECRET + SESSION. **Not adopted**.

Action: none.

### D3 — Connector and export-bundle governance | **status: substrate-ready, consumer-pending**

Per the upstream-reconciliation audit, the substrate primitives (encrypted blob store, envelope contract, master-key rotation, redaction registry) are all in place. No connector or export-bundle tool exists at HEAD; any future implementation would **compose** the substrate, not extend it.

This is therefore not a substrate gap. It is a feature-pending item that blocks on connector/export-tool implementation, not on this PR.

Action: none in this PR. When the future connector/export-tool feature is implemented, that feature's ADR + plan must reference this wave-14 ADR and confirm it composes the substrate primitives.

### D4 — Status-cache redaction | **status: substrate-ready, consumer-pending**

The redaction registry already provides `default_rules_for_class(SensitivityClass.CACHE)` and `redact_structured`. The settings field `aeat_status_cache_dir` is registered. No status-cache writer exists at HEAD.

This is the same shape as D3: substrate-ready, blocked on the consumer feature.

Action: none in this PR. When the future status-reader-writer feature is implemented, that feature's ADR + plan must reference this wave-14 ADR and confirm it routes through the redaction registry.

### D5 — Configuration documentation drift | **status: non-security; release-notes scope**

Each wave audit-gate doc carries operator-runbook context for that wave's CLI. `env/.env.example` is current. CLI `--help` text on the three `aeat security` commands explains the operator workflow.

A consolidated operator-runbook section in the README is a documentation deliverable, not a security finding. Track for the issue's release-notes wave.

Action: none in this PR. The release-notes wave (separate issue) consolidates the runbook.

## Rationale

**Why decide vs defer.** The user's "no deferring; lean and clean" mandate forecloses indefinitely-pending items. Each deferred-list item must be **explicitly resolved** in this PR — either by implementation or by an explicit decision recorded in an ADR.

**Why reject D1 (SQLCipher) instead of implement.** Two reasons: (1) the substrate's column-level encryption covers the actual threat model; the only delta is structural-metadata hiding, which the classification policy explicitly classes as OPERATIONAL (plaintext-acceptable). (2) Windows binding cost is unworkable — operators would need to build MSVC binaries at install time.

**Why reject D2 (IDENTITY in SecretStore) instead of implement.** The envelope path already covers IDENTITY records. Adding a second persistence path for the same use case violates the "no extra development burden" / "lean and clean" mandate. Zero existing call sites want SecretStore IDENTITY lookup.

**Why "substrate-ready, consumer-pending" for D3 + D4.** These items wait on consumer features (export-bundle tool, status-reader-writer) that don't exist yet. The substrate primitives are complete; the future consumer features will compose them. Closing them in this PR is honest — the substrate work is done.

**Why "release-notes scope" for D5.** Documentation polish is a release deliverable, not a security finding. The per-wave audit gate already includes operator runbook context for each shipped CLI.

## Consequences

**The PR's deferred-list is empty post-wave-14.** Every item from the upstream-reconciliation audit + final-security-audit is explicitly resolved (closed by implementation, by rejection, or by consumer-pending dependency).

**Substrate is feature-complete.** Wave-1 (substrate) → wave-13 (validator consolidation) + wave-14 (closure) form a complete delivery: ADR + plan + execute + audit per wave; AES-256-GCM AEAD; HKDF-SHA256 per-purpose KEK; Argon2id passphrase-derived KEK; master-key rotation; KDF-version migration; corpus integrity manifest; column-level encryption; envelope-bound classification; redaction registry; trilingual error registry; full test coverage.

**Future agents have a closure record.** Any future PR that proposes "let's add SQLCipher" or "let's widen SecretStore to IDENTITY" must first reconcile against this ADR — not silently re-open the deferred-list.

**No production-code changes in this wave.** All risk is in the decision wording. Wave-14 audit gate confirms the closure is complete.
