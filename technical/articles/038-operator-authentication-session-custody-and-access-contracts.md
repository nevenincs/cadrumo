# Operator authentication, session custody, and access contracts

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-038` · **Topic:** [Authentication and storage management](../topics/authentication-and-storage-management.md)

<!-- preserved:article -->
## Scope

This chunk covers 19 authentication application modules (5,680 lines; 43,176 measured o200k_base proxy tokens). I read all assigned ranges over eight bounded pages, splitting the two oversized outputs into line-bounded reads and completing the page that crossed the result-model boundary. Static inspection only: I did not invoke authentication, contact AEAT, load application modules, or test persistence adapters. No tests are included in this chunk.

## Operator outcomes and execution

Provider configuration resolves the active profile, refuses missing, dangling, or unhealthy profile pointers, and writes the provider preference plus workflow state and a typed bucket event through the workflow repository’s combined update path. A certificate path may be recorded as a filesystem reference, while passwords and keys are excluded. The profile fact update can bind to a revision-and-digest baseline; the preference helper rejects a partial baseline and applies the provider and optional Cl@ve route as one fact command. The internal configure result describes readiness, while its registered-operation projector reduces the filesystem path to a boolean and releases a strict, exact-profile result. Configuration service (`src/cadrumo/application/auth/operator.py`) Revision-bound preference write (`src/cadrumo/application/auth/preferences.py`) Public result projection (`src/cadrumo/application/auth/provider_configure_operation_access.py`)

Login first resolves a single auth projection snapshot, checks live-read opt-in and provider-local readiness, and then calls the provider session lifecycle. Certificate path/file and Cl@ve identity preconditions produce operator-safe typed refusals. Session writes are staged while browser/provider work runs; after it completes, the service enters the supplied effect guard, publishes the staged session and records verified workflow state with a bucket event. The operation definition supplies the human, exact-profile authority and one-shot secret boundary for profile login, passphrase rotation, configuration, acquisition, logout and reset. Provider composition is injected through a selector; browser, session-store and provider contracts keep concrete runtime types outside the application service. Login and staged publication (`src/cadrumo/application/auth/operator.py`) Provider preconditions (`src/cadrumo/application/auth/operator.py`) Operation executors and secret parsing (`src/cadrumo/application/auth/operation_definitions.py`) Provider boundary (`src/cadrumo/application/auth/providers.py`) Session-store staging contract (`src/cadrumo/application/auth/protocols.py`)

There are two deliberate layers here: the service function accepts an optional effect guard for trusted composition, while the registered acquisition operation applies the exact-profile human policy and passes the operation context into the service. To assess the practical authorization boundary, synthesis should trace all production callers and confirm untrusted CLI/TUI requests enter through that registered executor; the function signature alone does not establish a reachable bypass. Acquisition access resolver and result gate (`src/cadrumo/application/auth/session_acquire_operation_access.py`) Registered operation executor (`src/cadrumo/application/auth/operation_definitions.py`)

Status and test share the canonical state projection so that their configured/available answers are aligned. Test adds purely local checks: a persisted-session presence/expiry read, a certificate bundle health probe, or Cl@ve identity classification. The preflight report adds identity alignment and safe mode/configuration indicators; if no custody session is open it can return a degraded provider-only answer, but it refuses to report a different profile while another profile is open. The certificates and identity ports translate adapter outcomes to closed application records; these readiness probes do not contact AEAT. Status and test projection (`src/cadrumo/application/auth/operator.py`) Local certificate and Cl@ve probes (`src/cadrumo/application/auth/operator_probes.py`) Preflight scope behavior (`src/cadrumo/application/auth/operator.py`) Probe contracts (`src/cadrumo/application/auth/operator_probe_ports.py`)

The auth-read operation binds status, test and diagnostic reads to the exact profile in request, subject and active-bucket checks. It runs the local service in a worker thread, stores the typed result as an operand, and exposes a closed projection after validating a successful, no-effect receipt. Diagnostic details are delegated to the diagnostic service and its persistence port. The access resolver allows declared frontends/actions and reports only profile-value disclosure. Read executor (`src/cadrumo/application/auth/read_operation.py`) Exact-profile read policy and projection (`src/cadrumo/application/auth/read_operation.py`)

Logout and reset use durable cleanup intents. Intent creation snapshots the provider scope, session/lock presence, certificate-source names and registration timestamps, path/source state, and secret names. It uses a stable operation identity for resumption. Logout deletes scoped sessions and clears verified state only if its provider/configuration/authentication snapshot still matches. Reset additionally removes matching profile auth preference, locks, certificate-source secrets and witnessed source records, then appends typed workflow and bucket events. Source records are removed only while their name-and-registration witness still matches; cleanup results contain counts and provider IDs, not secret values. Intent planning and witnesses (`src/cadrumo/application/auth/operator_cleanup.py`) Intent construction (`src/cadrumo/application/auth/operator_cleanup.py`) Logout finalization (`src/cadrumo/application/auth/operator.py`) Reset sequence (`src/cadrumo/application/auth/operator.py`)

One cross-module follow-up is explicit in the reset implementation: reset currently clears acquisition locks with allow_held enabled, and the nearby comment says a held-lock concern was raised but a prior operator decision covered only login’s reset-lock path. Trace who can own a held lock, whether that owner is cancelled or prevented from publishing, and what invariant keeps the profile/session safe before treating this as a defect or changing the behavior. Held-lock reset call and scope note (`src/cadrumo/application/auth/operator.py`) Lock clearing helper (`src/cadrumo/application/auth/operator_cleanup.py`)

## Knowledge, data, and trust boundaries

The application obtains provider kinds from a closed catalogue, reads auth preference from the active profile’s fact record, and resolves Cl@ve credentials through the same resolver used for live sessions. Certificate checks use the configured path, secret and policy thresholds through an injected health port. The reports distinguish configured state from provider availability and local certificate/session readiness. This chunk contains no legal reference corpus and no model or LLM decision path; the auth decisions are typed rules and local observations. Provider credential resolution for probes (`src/cadrumo/application/auth/operator_probes.py`) Probe result vocabulary (`src/cadrumo/application/auth/probes.py`)

Session-domain records intentionally exclude browser storage material, but retain identity and verification facts: certificate thumbprint/subject, Cl@ve identity, observed landing URL, and for Cl@ve Móvil a QR confirmation code described as audit-only. These are sensitive operational facts even though they are not the browser token itself. The exact storage encryption, retention and adapter access policy are outside this chunk. Session detail records (`src/cadrumo/application/auth/session_types.py`) Session assertion and identity (`src/cadrumo/application/auth/session_types.py`)

## Security and implementation assessment

Strong controls visible locally include profile-and-storage-root matching before a service can reuse an open custody session; refusals rather than silently opening or borrowing a different profile; a per-bucket mutation span with same-thread re-entry checks; exact profile subjects and human access resolvers for registered mutations; effect-guarded publication after remote work; strict typed receipt validation; and result projection that removes private paths and secret material. Auth provider preference changes and durable events are coupled by one repository update, and cleanup records enough intent to retry after interrupted side effects. Custody routing (`src/cadrumo/application/auth/operator_scope.py`) Mutation ownership (`src/cadrumo/application/auth/operator_scope.py`) Configuration result closure (`src/cadrumo/application/auth/provider_configure_operation_access.py`)

Readiness probes are intentionally best-effort: expected local failures map to empty/unavailable states and debug logs. The certificate path probe first checks file existence and readability, then passes a SecretStr password to the injected certificate-health port. Some typed failure details are interpolated into localized summaries, so adapters and callers should continue ensuring that diagnostic detail is safe to expose. The result contracts are mostly strict and frozen, with incomplete configuration requiring a typed precondition verdict. Probe failure handling (`src/cadrumo/application/auth/operator_probes.py`) Result contracts (`src/cadrumo/application/auth/operator_results.py`)

No confirmed local defect is established by this chunk. The held-lock reset behavior and direct service-call reachability are scoped questions for cross-module tracing, not proof of a bypass or unsafe outcome. Storage encryption, lock-adapter atomicity, browser teardown, caller reachability, and end-to-end recovery behavior require inspection beyond these application modules. No runtime, integration, or test-suite evidence is claimed.

## Complete assigned-file coverage

- operation_definitions.py (709 lines) (`src/cadrumo/application/auth/operation_definitions.py`)
- operator.py (1,331 lines) (`src/cadrumo/application/auth/operator.py`)
- operator_cleanup.py (557 lines) (`src/cadrumo/application/auth/operator_cleanup.py`)
- operator_probe_ports.py (121 lines) (`src/cadrumo/application/auth/operator_probe_ports.py`)
- operator_probes.py (587 lines) (`src/cadrumo/application/auth/operator_probes.py`)
- operator_result_projections.py (201 lines) (`src/cadrumo/application/auth/operator_result_projections.py`)
- operator_results.py (440 lines) (`src/cadrumo/application/auth/operator_results.py`)
- operator_scope.py (366 lines) (`src/cadrumo/application/auth/operator_scope.py`)
- operator_scope_ports.py (94 lines) (`src/cadrumo/application/auth/operator_scope_ports.py`)
- output.py (38 lines) (`src/cadrumo/application/auth/output.py`)
- passphrase_operation_access.py (87 lines) (`src/cadrumo/application/auth/passphrase_operation_access.py`)
- preferences.py (75 lines) (`src/cadrumo/application/auth/preferences.py`)
- probes.py (33 lines) (`src/cadrumo/application/auth/probes.py`)
- protocols.py (225 lines) (`src/cadrumo/application/auth/protocols.py`)
- provider_configure_operation_access.py (135 lines) (`src/cadrumo/application/auth/provider_configure_operation_access.py`)
- providers.py (113 lines) (`src/cadrumo/application/auth/providers.py`)
- read_operation.py (257 lines) (`src/cadrumo/application/auth/read_operation.py`)
- session_acquire_operation_access.py (75 lines) (`src/cadrumo/application/auth/session_acquire_operation_access.py`)
- session_types.py (236 lines) (`src/cadrumo/application/auth/session_types.py`)
<!-- /preserved:article -->
