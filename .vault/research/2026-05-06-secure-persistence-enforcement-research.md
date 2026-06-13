---
tags:
  - '#research'
  - '#secure-persistence-enforcement'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-04-27-secure-persistence-foundation-research]]'
  - '[[2026-04-27-secure-persistence-foundation-adr]]'
  - '[[2026-04-27-secure-persistence-foundation-plan]]'
  - '[[secure-persistence-foundation.index]]'
  - '[[2026-04-30-secure-persistence-foundation-final-security-audit]]'
  - '[[2026-04-30-secure-persistence-foundation-final-security-resolution-audit]]'
  - '[[2026-04-30-secure-persistence-foundation-wave7-audit]]'
  - '[[2026-05-05-codebase-sanitization-audit]]'
---



# `secure-persistence-enforcement` research: `secure persistence enforcement`

This research backfills the current secure persistence hardening work and
grounds the next enforcement loop. It updates the older
`secure-persistence-foundation` framing with the live implementation state:
the project has moved beyond a substrate-only phase and now has many
production consumers migrated to encrypted SQL secure objects.

## Findings

### Encrypted SQL secure objects are the sensitive persistence center

`SecureObjectRepository` is the active sensitive persistence boundary. It
persists byte payloads in the SQL `secure_objects` table, stores natural keys
through `HashedLookup`, stores payloads through `EncryptedBytes`, and gates
reads and listings by `expected_class` and `max_supported_version`.

This makes the encrypted SQL secure-object backend the current target for
governed sensitive persistence. It supersedes earlier file-envelope framing
for migrated paths.

Evidence anchors: `src/aeat/adapters/persistence/storage/sql/secure_objects.py:31`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:67`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:91`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:116`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:190`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:196`,
`src/aeat/adapters/persistence/storage/sql/_orm.py:121`,
`src/aeat/adapters/persistence/storage/sql/_orm.py:142`,
`src/aeat/adapters/persistence/storage/sql/_orm.py:146`.

### The policy canary forbids direct sensitive file persistence

`src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
is a hard canary over selected sensitive production surfaces. It scans AST
calls and source text for direct write surfaces and older envelope helpers.

The forbidden surfaces include `write_text`, `write_bytes`, write or append
mode `open()`, `NamedTemporaryFile`, `mkstemp`, `save_envelope`,
`save_encrypted_envelope`, and `load_encrypted_envelope`.

This test encodes a stronger direction than the earlier position that
encrypted file envelopes could remain acceptable for governed sensitive data
in selected paths.

Evidence anchors:
`src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py:13`,
`src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py:37`,
`src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py:46`,
`src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py:80`,
`src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py:94`.

### Migrated domain repositories now route through secure objects

Profile ledgers use secure SQL objects. `inventory.py` stores `FINANCIAL`
ledgers under `aeat.persistence.profile.inventory`. `assets.py` stores
`FINANCIAL` asset and amortization ledgers under separate namespaces.
`tax_residence.py` stores `IDENTITY` profile JSON under
`aeat.persistence.profile.tax_residence`.

Setup profile persistence stores `AutonomoProfile` as an `IDENTITY` secure
object. It also guards real NIF writes against the unsecured deterministic
backend.

Major financial, filing, audit, workflow, and user CLI repositories currently
route through `SecureObjectRepository`. This includes transactions, invoices,
attachments, filing drafts, submissions, justificantes, usage ratios, workflow
runs, user CLI state, and filed-declaration observations.

### OPERATIONAL environment configuration remains an explicit file exception

The setup `.env` writer remains a controlled direct file writer for
`OPERATIONAL` configuration. Its scope is constrained to fixed owned keys plus
a comment naming the password environment variable. It does not write the
password value.

This exception is materially different from storing `SECRET`, `SESSION`,
`IDENTITY`, `FINANCIAL`, `AUDIT`, `CACHE`, `CORPUS`, or `DIAGNOSTIC` records
as plaintext files.

### Google credential material is secure-object backed

Google OAuth tokens, OAuth client JSON, and service-account JSON are `SECRET`
secure objects.

The service-account loader can still fall back to `from_service_account_file()`
when no secure cached payload exists. The service-account file path therefore
remains an input source, but helper save and load APIs are secure-object
backed.

### DIAGNOSTIC cache and usage persistence is encrypted but lossy

LLM cache and usage records are `DIAGNOSTIC` secure objects. They are redacted
through `default_rules_for_class(SensitivityClass.DIAGNOSTIC)` before save.

Cache reads return the redacted cached entry. This makes the cache
intentionally lossy. The behavior is redaction before encrypted SQL
secure-object persistence, not encryption of full diagnostic content.

### SESSION persistence routes through secure objects

AEAT browser session state is persisted as `SESSION` secure-object data.

Cl@ve Movil diagnostics also persist encrypted `SESSION` objects. The HTTPX
fallback fails closed instead of materializing PEM or key temporary files.

### Observability traces remain redacted filesystem persistence

Observability run trace storage is still filesystem-backed. `core/observability/_store.py`
redacts `DIAGNOSTIC` data before writing `trace.json` and `events.jsonl`, but
it persists redacted JSON and JSONL through `write_text` and append file
handles.

This is not the same as encrypted SQL secure-object persistence. Its
acceptability depends on whether redacted diagnostic filesystem artifacts
remain in scope as a permitted exception.

### Policy-test coverage is not complete

The current `_SENSITIVE_SURFACES` list does not cover every production writer
class named in the original broad audit. Known non-covered surfaces include
`src/aeat/core/observability/_store.py` and general locale or corpus writers.

Remaining audit work must decide which non-covered writers are governed by
secure persistence enforcement and which are intentionally outside the
sensitive persistence boundary.

## Current State

The live codebase has moved beyond the 2026-04-27 Wave-1 substrate state.
Many domain consumers have migrated to `SecureObjectRepository`.

The earlier vault artifacts remain useful as historical rationale and finding
ledger, but they are no longer exact implementation descriptions for migrated
paths. Later audit text that describes final findings as resolved through
`save_encrypted_envelope` should be treated as historical drift where live code
now uses SQL secure objects.

The active enforcement direction is now: governed sensitive persistence should
use the encrypted SQL secure-object backend unless it falls under a narrowly
documented exception.

## Terminology

Use `secure object`, `secure-object backend`, and `encrypted SQL
secure-object backend` for the live sensitive persistence target.

Use `file-envelope` only when referring to older substrate artifacts or
storage-envelope helpers.

Treat `store_dir`, `path`, `envelope_path`, `lock_target`, and
`db://secure_objects/...` returns in migrated repositories as logical
identifiers or compatibility markers, not materialized plaintext file
destinations.

Use sensitivity names that match `SensitivityClass`: `SECRET`, `SESSION`,
`IDENTITY`, `FINANCIAL`, `AUDIT`, `CACHE`, `CORPUS`, `OPERATIONAL`, and
`DIAGNOSTIC`.

Distinguish redaction from encryption. `core/observability/_store.py` is
redacted filesystem persistence. LLM cache, usage, and most governed
repositories are encrypted SQL secure objects.

## Required References

`src/aeat/adapters/persistence/storage/sql/secure_objects.py`

`src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`

`.vault/research/2026-04-27-secure-persistence-foundation-research.md`

`.vault/adr/2026-04-27-secure-persistence-foundation-adr.md`

`.vault/plan/2026-04-27-secure-persistence-foundation-plan.md`

`.vault/secure-persistence-foundation.index.md`

`.vault/audit/2026-04-30-secure-persistence-foundation-final-security-audit.md`

`.vault/audit/2026-04-30-secure-persistence-foundation-final-security-resolution-audit.md`

`.vault/audit/2026-04-30-secure-persistence-foundation-wave7-audit.md`

`.vault/audit/2026-05-05-codebase-sanitization-audit.md`
