# Configuration reset and diagnostics

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-026` · **Topic:** [Application orchestration and diagnostics](../topics/application-orchestration-and-diagnostics.md)

<!-- preserved:article -->
## Scope

This chunk covers 20 application files (5,273 lines), including durable all-profile reset orchestration, repair diagnostics, and registry-derived foreign-asset thresholds. I read all assigned ranges across nine bounded pages. Static review only; I did not execute destructive reset, CLI, or network paths. Legal accuracy is outside this review.

## Durable all-profile reset

`start_config_reset` requires explicit confirmation, snapshots the active profile pointer, discovers bucket IDs, includes a pointer-selected bucket even if discovery missed it, refuses an already-incomplete reset, and acquires deletion locks before preflight. Each target records its label, setup state, existence/fingerprint, retention decision, and phase in a credential-free journal. A retention block pauses the operation unless the caller explicitly acknowledges an override and supplies a non-empty reason. The decision model requires the blocking flag to match the retained-record count and binds override approval to a reason; this is internal record consistency, not external proof of policy authorization. Reset start and confirmation (`src/cadrumo/application/config_reset.py`) Preflight and override recording (`src/cadrumo/application/config_reset.py`) Retention decision model (`src/cadrumo/application/config_reset_models.py`)

The operation advances through recorded auth clearing, pointer reconciliation, and deletion phases. Resume re-reads the pointer and each nondeleted target. Pointer changes pause the operation; a changed target fingerprint is re-snapshotted and pauses for another explicit resume instead of silently carrying the previous approval forward. An approved override is dropped if the retained set grows beyond what the operator saw. Before deletion, the code refreshes retention and checks the retention backstop again. It writes an operation/bucket/fingerprint marker before invoking the profile-capsule lifecycle. If a crash leaves a target marked DELETING but the capsule absent, resume accepts completion only when the persisted marker attests to this same operation and bucket. Resume and pointer reconciliation (`src/cadrumo/application/config_reset.py`) Resume preflight (`src/cadrumo/application/config_reset.py`) Deletion marker and recovery (`src/cadrumo/application/config_reset.py`)

Auth cleanup distinguishes a locked profile from an unlocked one. Both clear plaintext acquisition locks outside the capsule. An unlocked target can also run full auth revocation and report how many out-of-capsule certificate-secret records were removed. A locked target records capsule destruction as the cleanup mode; its external certificate-secret count is unknown, not zero, because it cannot enumerate key-addressed records. The capsule deletion itself removes in-capsule auth rows. These modes make the remaining scope visible instead of claiming a full revocation that could not run. Auth cleanup modes (`src/cadrumo/application/config_reset.py`) Journaled clearance shape (`src/cadrumo/application/config_reset_models.py`)

The reset journal repository serializes creation and per-operation execution, rejects a second incomplete operation, and delegates atomic per-file replacement to the shared journal base. The repository explicitly does not make the entire multi-profile operation one atomic transaction or provide cryptographic journal authenticity. The Pydantic models validate status/phase correlations, sorted unique targets, marker ownership, completion counts, and timestamps, but do not enforce phase transitions; orchestration owns those. Journal repository contract (`src/cadrumo/application/config_reset_repository.py`) Operation-state consistency (`src/cadrumo/application/config_reset_models.py`)

## Diagnostics and recovery guidance

`aeat config repair` builds typed checks for Python/package/logging, secure workflow state, active-profile health, wizard/auth readiness, and per-namespace secure-object decryptability. It does not unlock a profile to make the report succeed. On locked/unreadable state it emits redacted profile-health outcomes; only a typed missing-session classification is downgraded to an expected cold-start warning. The model requires every warning/failure row to carry a structured actionable verdict or explicit no-recovery outcome, while OK rows carry none. Rendering reports diagnoses without reconstructing executable commands from error text. Diagnostic status contract (`src/cadrumo/application/diagnostic_models.py`) Repair report assembly (`src/cadrumo/application/diagnostics.py`) Quarantine operation (`src/cadrumo/application/diagnostics.py`)

Integrity probing aggregates counts from populated secure-object namespaces. Dry-run quarantine and committed quarantine use the same decryptability probe; quarantine preserves the encrypted payload and metadata in an archive table and does not auto-delete it. One local reporting weakness is visible: when the repository or engine cannot be reached, `_probe_secure_objects_integrity` returns an empty zero-count report, which the following check renders as `secure_objects_empty`/OK. A separate storage-state warning may still explain the outage, but this integrity row alone cannot distinguish “empty” from “unavailable”; preserve that uncertainty in the diagnostic result.

## Other application boundaries and assessment

The exception-precondition adapter follows structural Python/Pydantic exception links and only projects one unambiguous registered terminal verdict; otherwise it fails closed to a generic validation outcome. The application-level exchange-rate provider is a context-bound host factory, so currency conversion cannot silently construct its own network transport. Foreign-asset thresholds come from a caller-pinned bundled registry revision and date-scoped parameter declarations; the resulting threshold carries source/legal references and review status. The docstring says obligation assessment can use an unattested revision while filing has a separate review gate, and notes that a consumer currently does not surface the review notice. This code proves lookup/provenance behavior, not that legal values or references are current or correct. Nested exception verdict extraction (`src/cadrumo/application/cli_exception_preconditions.py`) Host-composed rate provider (`src/cadrumo/application/exchange_rate_provider.py`) Registry threshold resolution (`src/cadrumo/application/foreign_asset_thresholds.py`)

The strongest local qualities are durable phase recording with resume checks, explicit retention override records, cleanup modes that admit unknown residue, typed actionable diagnostic results, and exact-profile operation scoping. Remaining verification should cover crash points across reset phases, journal tampering/locking, all-profile concurrent mutation, diagnostic unavailable-versus-empty reporting, receipt destinations, and every caller of unattested threshold values. No assigned tests or runtime evidence were included here.

## Complete assigned-file coverage

All 20 assigned files were read in full across pages 1–9.

- application/__init__.py (3 lines) (`src/cadrumo/application/__init__.py`)
- _state_projection_readiness.py (24 lines) (`src/cadrumo/application/_state_projection_readiness.py`)
- auth_credentials.py (34 lines) (`src/cadrumo/application/auth_credentials.py`)
- bucket_deletion_contracts.py (34 lines) (`src/cadrumo/application/bucket_deletion_contracts.py`)
- bucket_event_projection.py (90 lines) (`src/cadrumo/application/bucket_event_projection.py`)
- bucket_event_repository.py (52 lines) (`src/cadrumo/application/bucket_event_repository.py`)
- cli_exception_preconditions.py (207 lines) (`src/cadrumo/application/cli_exception_preconditions.py`)
- config_reset.py (1,056 lines) (`src/cadrumo/application/config_reset.py`)
- config_reset_models.py (373 lines) (`src/cadrumo/application/config_reset_models.py`)
- config_reset_repository.py (153 lines) (`src/cadrumo/application/config_reset_repository.py`)
- diagnostic_models.py (236 lines) (`src/cadrumo/application/diagnostic_models.py`)
- diagnostics.py (960 lines) (`src/cadrumo/application/diagnostics.py`)
- diagnostics_operation.py (809 lines) (`src/cadrumo/application/diagnostics_operation.py`)
- diagnostics_operation_ports.py (51 lines) (`src/cadrumo/application/diagnostics_operation_ports.py`)
- diagnostics_ports.py (66 lines) (`src/cadrumo/application/diagnostics_ports.py`)
- diagnostics_run_health.py (756 lines) (`src/cadrumo/application/diagnostics_run_health.py`)
- diagnostics_run_health_ports.py (82 lines) (`src/cadrumo/application/diagnostics_run_health_ports.py`)
- application/errors.py (32 lines) (`src/cadrumo/application/errors.py`)
- exchange_rate_provider.py (63 lines) (`src/cadrumo/application/exchange_rate_provider.py`)
- foreign_asset_thresholds.py (192 lines) (`src/cadrumo/application/foreign_asset_thresholds.py`)
<!-- /preserved:article -->
