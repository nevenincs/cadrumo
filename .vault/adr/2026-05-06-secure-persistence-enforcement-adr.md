---
tags:
  - '#adr'
  - '#secure-persistence-enforcement'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-secure-persistence-enforcement-research]]'
  - '[[2026-04-27-secure-persistence-foundation-research]]'
  - '[[2026-04-27-secure-persistence-foundation-adr]]'
  - '[[2026-04-27-secure-persistence-foundation-plan]]'
  - '[[secure-persistence-foundation.index]]'
  - '[[2026-04-30-secure-persistence-foundation-final-security-audit]]'
  - '[[2026-04-30-secure-persistence-foundation-final-security-resolution-audit]]'
  - '[[2026-04-30-secure-persistence-foundation-wave7-audit]]'
  - '[[2026-05-05-codebase-sanitization-audit]]'
---



# `secure-persistence-enforcement` adr: `secure persistence enforcement` | (**status:** `accepted`)

## Problem Statement

The live implementation now uses `SecureObjectRepository` as the primary
sensitive persistence boundary. The repository persists encrypted byte payloads
in SQL `secure_objects`, stores natural keys through `HashedLookup`, and gates
load and list operations by `expected_class` and `max_supported_version`.

Many domain repositories have migrated to secure objects, including profile
ledgers, setup profile persistence, Google credential helpers, LLM cache and
usage records, AEAT browser session state, Cl@ve Movil diagnostics, financial
records, filing records, audit records, workflow state, and user CLI state.

The current sensitive-persistence policy test also encodes a hardening
direction. It forbids direct file writes, temporary file materialization, and
older envelope helper calls across configured sensitive surfaces.

Earlier vault artifacts describe the foundation and Wave-1 substrate state.
They remain valid historical rationale but no longer fully describe the live
implementation. The current enforcement target is stronger and more specific:
governed sensitive persistence should go through the encrypted SQL
secure-object backend.

## Considerations

The accepted backend is `SecureObjectRepository` backed by SQL
`secure_objects`, `HashedLookup`, and `EncryptedBytes`, with class and version
gating on reads.

The sensitive-persistence policy test makes direct file writes a failing
condition for selected sensitive production surfaces. This converts security
review expectations into an executable guard.

Compatibility markers such as `store_dir`, `path`, `envelope_path`,
`lock_target`, and `db://secure_objects/...` remain useful for CLI display,
API compatibility, and logical identity. They must not be interpreted as
authority to create plaintext sensitive file destinations.

The setup `.env` writer remains a controlled direct-file exception for
`OPERATIONAL` configuration. Explicit user-directed exports are also boundary
crossings, not normal repository persistence.

Redacted `DIAGNOSTIC` observability traces remain unresolved. Redaction is not
encryption, and `core/observability/_store.py` still writes filesystem
artifacts.

## Constraints

Governed records in `SECRET`, `SESSION`, `IDENTITY`, `FINANCIAL`, `AUDIT`,
`CACHE`, `CORPUS`, and in-scope `DIAGNOSTIC` classes must not persist through
direct plaintext file writes, ad hoc temporary files, or older
storage-envelope helpers when they are inside sensitive production surfaces.

The setup `.env` exception is constrained to fixed owned keys and a comment
naming the password environment variable. It must not write password values or
other governed sensitive payloads.

Explicit user-directed exports are permitted only when the user intentionally
asks the system to materialize data outside the secure-object backend. Such
exports must be distinguishable from normal repository persistence.

Service-account file paths may remain input sources for loaders when no secure
cached payload exists. Helper save and load APIs for Google credential material
remain secure-object backed.

## Implementation

Accept the encrypted SQL secure-object backend as the mandatory persistence
boundary for governed sensitive records.

Continue expanding the policy canary until all governed production writers are
covered or explicitly documented as out of scope. The canary should continue
to reject direct sensitive use of `write_text`, `write_bytes`, write or append
mode `open()`, `NamedTemporaryFile`, `mkstemp`, `save_envelope`,
`save_encrypted_envelope`, and `load_encrypted_envelope`.

Classify every newly discovered write surface by `SensitivityClass`,
operational role, export intent, or non-sensitive status. Separate normal
repository persistence from explicit user-directed export behavior. Separate
loader input paths from persistence outputs.

Resolve redacted `DIAGNOSTIC` observability filesystem persistence through a
follow-up decision. The outcome must state whether redacted diagnostic
filesystem artifacts are accepted as an explicit exception, moved to secure
objects, or split by diagnostic subtype and retention requirement.

## Rationale

The encrypted SQL secure-object backend is already the center of the live
hardening work and supports the requirements that matter for sensitive local
data: encrypted payload storage, keyed natural lookup, sensitivity-class
validation, and schema-version validation at read time.

For sensitive production surfaces, older file-envelope helpers are now a
regression risk. They create an alternate persistence path that is harder to
audit and contradicts the current policy test. Treating secure objects as the
mandatory boundary gives future work one target and makes bypasses easier to
detect programmatically.

The exceptions are narrow because they are different classes of operation:
`.env` writes are operational configuration, and explicit exports are user
requested boundary crossings. Neither exception authorizes repositories to
write sensitive app state as ordinary files.

## Consequences

Sensitive persistence reviews should evaluate repositories against the
secure-object backend, not the older encrypted file-envelope model.

Policy tests should continue expanding `_SENSITIVE_SURFACES` until all
governed production writers are covered or explicitly documented as out of
scope.

Audits should identify remaining direct write surfaces and classify them by
`SensitivityClass`, operational necessity, export intent, or non-sensitive
status.

Any future repository that persists governed sensitive state must use
`SecureObjectRepository` or another backend accepted as equivalent by a later
ADR.

Documentation that still frames `save_encrypted_envelope` as the final
resolution for migrated sensitive paths should be treated as historical, not
normative.
