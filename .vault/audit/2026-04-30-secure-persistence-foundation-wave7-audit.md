---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave6-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-wave5-adr]]"
---



# `secure-persistence-foundation` wave-7 audit gate | (**status:** `passed`)

## Summary

Wave 7 closes the biggest deferred item from waves 1-6: ciphertext-
payload at rest. The wave-1 ADR explicitly flagged this as deferred,
the wave-3 audit gate's HIGH-1 finding recorded "ADR drift on
encryption-at-rest", and every subsequent ADR carried it forward.

Wave 7 lands two stages back-to-back:

- **Substrate** (commit `754047f`): adds
  ``save_encrypted_envelope`` / ``load_encrypted_envelope`` /
  ``CipherEnvelope`` to ``aeat.adapters.persistence.storage``. AES-256-GCM via
  ``encrypt_record``, per-consumer keys via HKDF-SHA256, AAD binding
  on (classification, hkdf_context). 8 substrate-level tests cover
  round-trip, no-plaintext-leak, classification gate, AAD-binding
  tamper detection, key-mismatch rejection, version gate, and class
  relabel attack.
- **Consumers** (commit `ce99130`): every governance repository
  delivered across waves 3-4 now writes ciphertext-at-rest:
  ``TransactionCatalogueRepository``, ``FilingDraftRepository``,
  ``FilingAmendmentRepository``, ``FilingHistoryRepository``,
  ``JustificanteRepository``, ``SubmissionRepository``. Each declares
  a distinct HKDF context. 119 repository + integration tests pass
  with explicit NIF/CSV/draft-id leak canaries on every persisted
  envelope.

Plus the merge-from-main commit (`6890a18`): integrated upstream PR
#432 (live-submit permanently forbidden) and excised the now-obsolete
wave-4 phase-5 ``GovernedLiveSubmitAuditSink`` and wave-5 phase-3
``_audit`` deprecation wrapper. With no live-submit emissions, those
sinks have no use case.

## Findings

### CARRY-FORWARDS — CLOSED

The following items were carried forward across multiple waves and are
now closed:

- **Ciphertext-payload at rest** — every governance repository now
  writes AES-256-GCM ciphertext. Confirmed end-to-end with NIF /
  amount / CSV / counterparty canaries on every persisted envelope.
- **Legacy ``_audit`` writer excision** — closed by upstream main
  merge.
- **Wave-4 phase 5 obsolescence** — the live-submit governed audit
  sink is deleted because live-submit is permanently forbidden.

### Cross-cutting design checks — PASS

- **AAD binding** — every ciphertext envelope authenticates both its
  sensitivity class and its consumer's HKDF context. Cross-consumer
  ciphertext substitution and class relabel attacks both fail with
  ``DecryptionError`` (verified by 2 dedicated substrate tests +
  5 per-repository ``test_foreign_class_envelope_refused`` tests).
- **Per-consumer key derivation** — distinct HKDF contexts:
  ``aeat.domain.financial.transactions.catalogue.v1``,
  ``aeat.application.filing.draft.v1``,
  ``aeat.application.filing.amendment.v1``,
  ``aeat.application.filing.history.v1``,
  ``aeat.domain.justificante.metadata.v1``,
  ``aeat.adapters.outbound.aeat.export.filing.v1``. Sharing the master key but not the
  derived key is the correct posture.
- **Test discipline** — ``EphemeralMasterKeyProvider`` continues to
  back every test; the new ``_resolve_master_key_provider()`` helper
  honours the existing ``override_master_key_provider()`` override
  mechanism so tests don't need to thread a provider into every
  repository constructor.
- **Migration helpers** — every legacy plaintext consumer's migration
  helper now writes ciphertext on the destination side. Operators
  who already migrated to plaintext envelopes via wave-3/4 will need
  a one-time re-encrypt pass; that helper is on the wave-8 list.
- **Idempotent re-saves** — verified across all 6 repositories.
- **Concurrency under per-record lock** — verified by the existing
  lock-isolation tests (wave-7 wiring is a writer change, the lock
  contract is unchanged).

### Pre-existing failures (NOT wave-7 regressions)

The full unit-suite shows 2 failures in
``src/aeat/entrypoints/mcp/test_launch_google_workspace.py``. Confirmed by stash-
testing the pre-merge state: these are a ``greenlet``/Playwright
library version incompatibility, not introduced by wave-7. They
predate the merge and are outside the wave-7 / persistence scope.

### No new HIGH/MEDIUM findings

This pass surfaced no new HIGH or MEDIUM findings on the wave-7
surface area. The substrate is solid; the repositories are
ciphertext-at-rest end-to-end; the AAD discipline defeats relabel
and cross-consumer attacks.

## Remaining deferred items (Wave-8 candidates)

Captured here so future waves can pick them up:

- **Re-encrypt migration helper** — one-time re-encrypt pass for
  operators who already have plaintext envelopes from wave-3/4
  builds. Read each plaintext envelope, re-write through the
  encrypted helper.
- **Status-cache redaction** — ``aeat_status_cache_dir`` setting
  exists but no writer consumes it yet; will revisit when a status
  reader lands.
- **Corpus integrity manifest** — top-level SHA-256 manifest for
  ``aeat_casillas_root`` / ``aeat_manuals_root``. The per-record
  hashing is already in place; only the directory-level manifest
  is missing.
- **Master-key rotation** — re-key path that re-derives every per-
  consumer key under a new master key without operator data loss.
  Requires re-encrypt across every repository.
- **Argon2id KDF / SQLCipher** — separate ADR; both require new
  runtime dependencies which the project's "no new deps" mandate
  has historically gated on user approval.
- **IDENTITY-class records in the secret store widening** — separate
  ADR.

## Decision

Wave 7 audit gate: **PASSED**. The most-deferred load-bearing claim
of the secure-persistence-foundation feature (ciphertext at rest for
governance-class records) is now backed by code, contracts, and
tests.

The rolling-wave loop continues. Wave 8 picks up the re-encrypt
migration helper and master-key rotation.
