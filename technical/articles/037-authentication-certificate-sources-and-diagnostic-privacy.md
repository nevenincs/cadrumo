# Authentication, certificate sources, and diagnostic privacy

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-037` · **Topic:** [Authentication and storage management](../topics/authentication-and-storage-management.md)

<!-- preserved:article -->
## Scope

This chunk covers 26 auth application modules (6,012 lines; 47,556 measured o200k_base proxy tokens): acquisition locking, local authentication status, apoderado representation, named certificate sources and secrets, and encrypted auth diagnostics. I read every assigned range over nine bounded pages, splitting the one oversized page into line-bounded reads. Static analysis only; I did not invoke authentication, contact AEAT, or inspect persistence adapters.

## Authentication and representation capabilities

The acquisition lock is filesystem-backed and shared across CLI processes. It creates the lock exclusively, includes provider/profile/process/host and expiry metadata but no credentials, refuses a live lock rather than risking a duplicate Cl@ve petition, and expires locks by TTL or a dead same-host PID. Stale removal compares the bytes inspected before deletion, and retries account for Windows sharing behavior. Lock inspection and stale classification (`src/cadrumo/application/auth/acquisition_lock.py`) Acquire/release lifecycle (`src/cadrumo/application/auth/acquisition_lock.py`) Compare-before-delete helper (`src/cadrumo/application/auth/acquisition_lock.py`)

There is a concrete race in the unreadable-record recovery path. An initial OSError marks the lock corrupt and recoverable while returning no observed bytes. If the file becomes readable and is replaced with a live lock before removal, the compare-and-delete helper skips its equality check because the expected text is None, then deletes the new contents. The acquiring process can then retry exclusive creation and proceed while the live owner still believes it holds the lock. That defeats the duplicate-petition protection under this specific unreadable-to-readable replacement sequence. Preserve an explicit unreadable observation state and refuse deletion when a later read becomes possible, then test a transient read failure followed by replacement with a valid unexpired record. Unreadable inspection result (`src/cadrumo/application/auth/acquisition_lock.py`) Acquire recovery branch (`src/cadrumo/application/auth/acquisition_lock.py`) Missing comparison for None (`src/cadrumo/application/auth/acquisition_lock.py`)

Apoderado configuration is local and per profile. The two-page flow collects a represented party's tax identity and a catalogue-backed scope set in memory, has no checkpoint, and commits through one service that validates identity and deduplicates scopes. The operation path rechecks exact profile identity, consumes the represented NIF through a one-use secret slot, runs the save/delete within an irreversible section, and binds result projection to a matching terminal receipt. Scope and identity errors are typed prewrite refusals. The advertised live check is not implemented: it always refuses, and the service has no AEAT mutation verb. Flow and no-checkpoint contract (`src/cadrumo/application/auth/apoderado_flow.py`) Configuration and live-check limit (`src/cadrumo/application/auth/apoderado_service.py`) Worker custody (`src/cadrumo/application/auth/apoderado_execution.py`) Exact-profile operation policy (`src/cadrumo/application/auth/apoderado_operation.py`)

The named certificate-source registry supports register/re-point, list, select and remove, with local health checks for every registered certificate. Selecting a named certificate routes credentials through the witnessed active-profile state; each named passphrase comes only from the profile-scoped secret backend and never falls back to the global unnamed password. The local probe reports missing/unreadable/expired/expiring certificate states without contacting AEAT. Registry transformations (`src/cadrumo/application/auth/certificate_sources.py`) Source health and secret resolution (`src/cadrumo/application/auth/certificate_source_operations.py`) Witnessed credential route (`src/cadrumo/application/auth/credentials.py`)

The source mutations update workflow state together with typed bucket events under active-profile, recovery and mutation guards. Selecting a source is separate from selecting the certificate auth provider; removing the active source clears that selection and prevents a same-path legacy unnamed credential from remaining effective. Auth-read requests are also credential-free and closed: a provider selector is accepted only for status/test, a diagnostic ID only for a detail view, and the response schema must match the requested kind. Event-backed registry mutation (`src/cadrumo/application/auth/certificate_source_operations.py`) Active selection and removal (`src/cadrumo/application/auth/certificate_sources.py`) Closed auth-read requests/results (`src/cadrumo/application/auth/auth_read_contracts.py`)

Certificate passphrase updates use a durable secret-free intent, a backend request witness for matching retries, a completion witness, and a final event that clears the intent. The passphrase itself is supplied through a short-lived ephemeral secret, is wrapped in SecretStr for the backend, and is absent from workflow state and result payloads. Set/remove operations are exact-profile, human-authorized, and protected by the auth mutation span; the backend is an application port whose encryption details are outside this chunk. Secret mutation boundary (`src/cadrumo/application/auth/certificate_secret_operation.py`) Intent, retry and completion lifecycle (`src/cadrumo/application/auth/certificate_source_operations.py`) Durable mutation state (`src/cadrumo/application/auth/models.py`)

## Diagnostic reads and reporting

Auth diagnostics may contain raw HTML, screenshots, route facts and identity hints, but persistence is behind an encrypted profile-scoped port. Listing returns summaries; detail returns only a bounded HTML placeholder and identity/path fingerprints. URL summaries omit query values, profile IDs are suppressed or fingerprinted, and persisted timestamps and phone-state values are validated before projection. A browser-observed phone state is accepted only with an authenticated-landing source and UTC observation instant; an operator report is used only when no browser state exists. Redacted summary/detail operations (`src/cadrumo/application/auth/diagnostics.py`) Detail redaction (`src/cadrumo/application/auth/diagnostics.py`) Phone-state source validation (`src/cadrumo/application/auth/diagnostics.py`)

Malformed encrypted payloads are rejected with typed validation errors rather than partially displayed, and old optional payload fields remain readable when valid. A detail view without a phone-state observation carries a structured operator-decision verdict; the report operation updates the existing encrypted record instead of writing a separate plaintext report. Payload decoding and UTC checks (`src/cadrumo/application/auth/diagnostics.py`) Report update preparation (`src/cadrumo/application/auth/diagnostics.py`) Report receipt validation (`src/cadrumo/application/auth/diagnostic_report_operation.py`)

The registered phone-state report operation requires the exact profile and a human-access policy, prepares the encrypted payload update before entering the irreversible save, and emits a typed not-found refusal when the diagnostic does not exist. Read requests similarly return only closed projection models, with detail fields and operator findings explicitly typed. Report executor and guarded persistence (`src/cadrumo/application/auth/diagnostic_report_operation.py`) Report access policy (`src/cadrumo/application/auth/diagnostic_report_operation.py`) Read projection contracts (`src/cadrumo/application/auth/auth_read_contracts.py`)

The modules show strong exact-profile routing, typed receipts, secret redaction and explicit live-operation limits. Storage encryption, filesystem permissions and backend concurrency are adapter responsibilities and were not tested. The lock race above is the primary confirmed local defect; no other issue is inferred from a missing implementation detail. No tests are in the assigned set. The external authority/catalogue material is not independently verified.

## Coverage appendix

- auth/__init__.py (3 lines) (`src/cadrumo/application/auth/__init__.py`)
- auth/_mutation.py (56 lines) (`src/cadrumo/application/auth/_mutation.py`)
- auth/acquisition_lock.py (480 lines) (`src/cadrumo/application/auth/acquisition_lock.py`)
- auth/actions.py (50 lines) (`src/cadrumo/application/auth/actions.py`)
- auth/apoderado_contracts.py (257 lines) (`src/cadrumo/application/auth/apoderado_contracts.py`)
- auth/apoderado_execution.py (301 lines) (`src/cadrumo/application/auth/apoderado_execution.py`)
- auth/apoderado_flow.py (238 lines) (`src/cadrumo/application/auth/apoderado_flow.py`)
- auth/apoderado_operation.py (265 lines) (`src/cadrumo/application/auth/apoderado_operation.py`)
- auth/apoderado_repository.py (45 lines) (`src/cadrumo/application/auth/apoderado_repository.py`)
- auth/apoderado_service.py (278 lines) (`src/cadrumo/application/auth/apoderado_service.py`)
- auth/apoderado_text.py (24 lines) (`src/cadrumo/application/auth/apoderado_text.py`)
- auth/auth_read_contracts.py (207 lines) (`src/cadrumo/application/auth/auth_read_contracts.py`)
- auth/catalogue.py (122 lines) (`src/cadrumo/application/auth/catalogue.py`)
- auth/certificate_secret_backend.py (67 lines) (`src/cadrumo/application/auth/certificate_secret_backend.py`)
- auth/certificate_secret_operation.py (335 lines) (`src/cadrumo/application/auth/certificate_secret_operation.py`)
- auth/certificate_source_contracts.py (161 lines) (`src/cadrumo/application/auth/certificate_source_contracts.py`)
- auth/certificate_source_execution.py (206 lines) (`src/cadrumo/application/auth/certificate_source_execution.py`)
- auth/certificate_source_operation.py (448 lines) (`src/cadrumo/application/auth/certificate_source_operation.py`)
- auth/certificate_source_operations.py (795 lines) (`src/cadrumo/application/auth/certificate_source_operations.py`)
- auth/certificate_sources.py (175 lines) (`src/cadrumo/application/auth/certificate_sources.py`)
- auth/credentials.py (310 lines) (`src/cadrumo/application/auth/credentials.py`)
- auth/diagnostic_report_operation.py (341 lines) (`src/cadrumo/application/auth/diagnostic_report_operation.py`)
- auth/diagnostics.py (564 lines) (`src/cadrumo/application/auth/diagnostics.py`)
- auth/diagnostics_ports.py (58 lines) (`src/cadrumo/application/auth/diagnostics_ports.py`)
- auth/errors.py (36 lines) (`src/cadrumo/application/auth/errors.py`)
- auth/models.py (190 lines) (`src/cadrumo/application/auth/models.py`)
<!-- /preserved:article -->
