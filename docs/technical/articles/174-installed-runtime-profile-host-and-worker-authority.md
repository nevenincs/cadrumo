# Installed runtime, profile host, and worker authority

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-174` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 19 runtime modules, 5,544 lines and 47,532 measured `o200k_base` proxy tokens. Every manifest range was read in nine bounded pages. The review is static: no runtime process was started and no native login, storage, IPC or worker behavior was exercised. These modules define the installed runtime’s bootstrap and host, connection/login lifecycle, profile worker, canonical operation dispatch, access management, enrollment/approval, and bounded shutdown.

## Runtime topology and capabilities

The installed entrypoint starts an isolated interpreter, filters ambient Python and dynamic-loader variables, disables Pydantic plugins, and uses a fixed Python module command without a shell. The runtime verifies its installed package version, requires an absolute storage root whose endpoint identity matches the requested identity, and chooses the platform-native endpoint. It builds the production operation registry before serving. A shutdown watchdog is armed around service; managed-stop hooks are composed where available. A Linux guardian checks the parent’s owner and process start identity, opens a pidfd, rechecks the exact process, then launches a contained worker with a minimal environment and no inherited descriptors (`bootstrap.py` (`src/cadrumo/entrypoints/runtime/bootstrap.py`), `main.py` (`src/cadrumo/entrypoints/runtime/main.py`), `linux_worker_guardian.py` (`src/cadrumo/entrypoints/runtime/linux_worker_guardian.py`)). This is strong process-boundary evidence in source, but OS behavior still requires platform tests.

`RuntimeProfileConnections` distinguishes each native connection, login evidence, client ID, profile and frontend. It lazily opens installation/profile custody only after a request, verifies OS owner and current automation-profile binding, and reuses a cached host only if the binding is unchanged. Password/receipt login is limited to CLI/TUI; a persisted human receipt is permitted only with password login. API-key routing can identify a candidate client from protected state, but the established authority still verifies the key and grants the lease. Password and receipt bytes travel through secret frames rather than ordinary request documents. Session refresh, lock, status, logout/connection loss, lock-generation change and periodic login observation retire stale access. A runtime that loses all positive unattended-login witnesses after seeing an eligible login sets its stop event (`profile_connections.py` (`src/cadrumo/entrypoints/runtime/profile_connections.py`), `profile_connections.py` (`src/cadrumo/entrypoints/runtime/profile_connections.py`)).

Profile access management wraps canonical services for session inventory, automation denial, global profile recovery preparation, and password-proven profile resume. Global denial is serialized by the profile guard; its in-memory denial fence is set before fallible durable publication, so a storage failure does not reopen the live process. Recovery is a separate no-session journey: it binds native login evidence, records a lock generation, sends a secret-ready signal, reads one password frame, and resumes only against that generation. Enrollment requests are tied to a live native connection, profile binding, OS owner, originating login, expiry and lock generation; they have bounded offer/record counts, use strict duplicate-free JSON parsing, and deliver one-time recipient work through a volatile protected channel. The handler retires offers on disconnect, expiry, lock or profile replacement. A helper `request()` path in worker automation administration is explicitly unavailable in this snapshot; that request door is not implemented by the worker adapter (`access_management.py` (`src/cadrumo/entrypoints/runtime/access_management.py`), `enrollment_connections.py` (`src/cadrumo/entrypoints/runtime/enrollment_connections.py`), `automation_execution.py` (`src/cadrumo/entrypoints/runtime/automation_execution.py`)).

## Operation execution and disclosure authority

The profile host composes one pinned registry/authority, session owner, worker process and operation services per exact profile binding. It requires a readable current recovery inventory before the first hosted private operation; damaged, stale or refused entries block that path. On submission, the host binds the new operation ID to the exact session, frontend and typed request, then admits it under a `SUBMIT` guard. It captures admission provenance—including scope, authority generation, and a payload fingerprint—and retains the original response capability only in the same process. Replays do not revive that capability. Start, resume, commit, response, review and result access re-resolve current registered policy and authority; stored invocation identity and profile binding are checked before disclosure (`operation_host.py` (`src/cadrumo/entrypoints/runtime/operation_host.py`), `operation_authority.py` (`src/cadrumo/entrypoints/runtime/operation_authority.py`)).

The worker-side authority holds grants in task-local guards, so child tasks inherit no authorization permit. It checks definition and subject identity, exact invocation provenance, current authority generation, profile binding and operation scope at each relevant boundary. COMMIT guards retain native authority and stable custody through an effect. One-shot secret submission verifies the exact admitted submitter/definition/subject and expires after its declared deadline; the worker wipes its mutable buffer in a `finally` path. The host preflights before signaling the frontend, then releases the profile fence while waiting for secret bytes or worker callbacks and obtains fresh authorization for delivery and acknowledgement. Result and review projections are serialized under a matching disclosure guard, and response apply/reject/inspect require the original local response capability (`operation_authority.py` (`src/cadrumo/entrypoints/runtime/operation_authority.py`), `operation_host.py` (`src/cadrumo/entrypoints/runtime/operation_host.py`), `operation_projection.py` (`src/cadrumo/entrypoints/runtime/operation_projection.py`), `profile_connections.py` (`src/cadrumo/entrypoints/runtime/profile_connections.py`)).

Operation payload uploads use a four-slot semaphore, bounded deadlines and a host-generated upload ID. Each chunk is read as a secret frame, length-checked, staged in the worker, and rechecked against the session; abandoned uploads close only that frontend stream and trigger bounded abort cleanup. The isolated worker validates its live native parent before opening custody, uses two channels in the same verified runtime cohort, installs an exact profile lease, and routes typed submit/start/resume/observe/project/manage requests through the canonical operation host. Periodic expiry retires staged payloads and expired proof candidates. Worker failure and task cleanup retain cleanup owners rather than silently dropping failed releases (`submission_stream.py` (`src/cadrumo/entrypoints/runtime/submission_stream.py`), `worker.py` (`src/cadrumo/entrypoints/runtime/worker.py`), `worker.py` (`src/cadrumo/entrypoints/runtime/worker.py`)).

Automation approval follows a separate multi-phase path. The worker creates its cleanup proxy before the first cancellable exchange; proof preparation, recipient inspection and delivery occur outside publication authority. Review/candidate/activation/decline publication requires the same task’s held human `COMMIT` lease. Parent-side checks bind worker, runtime boot, profile, connection, session, operation and review digest; recipient consent is re-read before scoped delegation, and cleanup can retire a proof after expiry or disconnect (`automation_execution.py` (`src/cadrumo/entrypoints/runtime/automation_execution.py`), `profile_host.py` (`src/cadrumo/entrypoints/runtime/profile_host.py`)).

## Shutdown and implementation assessment

Shutdown stops new admissions, closes enrollment delivery, drains each worker under a deadline, retains original request/containment threads for retries, and only clears ownership after no worker is uncontained or unsettled. If the runtime cannot settle within its watchdog deadline, `terminate_runtime()` exits the installed process so root ownership is not released while callbacks or child processes may continue. This is a meaningful fail-closed containment design; its assurance depends on real Linux/Windows process and named-pipe behavior, which static reading cannot certify (`profile_connections.py` (`src/cadrumo/entrypoints/runtime/profile_connections.py`), `shutdown.py` (`src/cadrumo/entrypoints/runtime/shutdown.py`)).

The code has strong separation of ordinary documents from secret frames, verified peer and boot identity, exact profile/session scoping, fresh authorization on private effects and disclosures, fail-closed uncertainty, and retained cleanup state. It is also large and concurrency-heavy: admission, cancellation, callback, profile replacement and drain logic span parent, worker and OS-specific adapters. No tests are included in these assigned files. Synthesis should inspect worker-authorization IPC framing and schemas, custody-store atomicity/locking, candidate-key lifetime, Windows containment/handle inheritance, Linux guardian and pidfd behavior, response capability storage, and every operation handler that uses this boundary. Review race tests for disconnect during secret upload, denial during COMMIT, profile-root replacement during worker callbacks, shutdown during construction, and interrupted native approval delivery.

## Complete assigned-file coverage

All 19 assigned files were fully read at their manifest-specified line ranges:

- `__init__.py` (`src/cadrumo/entrypoints/runtime/__init__.py`)
- `__main__.py` (`src/cadrumo/entrypoints/runtime/__main__.py`)
- `access_management.py` (`src/cadrumo/entrypoints/runtime/access_management.py`)
- `automation_execution.py` (`src/cadrumo/entrypoints/runtime/automation_execution.py`)
- `bootstrap.py` (`src/cadrumo/entrypoints/runtime/bootstrap.py`)
- `enrollment_connections.py` (`src/cadrumo/entrypoints/runtime/enrollment_connections.py`)
- `gnome_login_observer.py` (`src/cadrumo/entrypoints/runtime/gnome_login_observer.py`)
- `linux_worker_guardian.py` (`src/cadrumo/entrypoints/runtime/linux_worker_guardian.py`)
- `main.py` (`src/cadrumo/entrypoints/runtime/main.py`)
- `operation_authority.py` (`src/cadrumo/entrypoints/runtime/operation_authority.py`)
- `operation_host.py` (`src/cadrumo/entrypoints/runtime/operation_host.py`)
- `operation_projection.py` (`src/cadrumo/entrypoints/runtime/operation_projection.py`)
- `profile_connections.py` (`src/cadrumo/entrypoints/runtime/profile_connections.py`)
- `profile_host.py` (`src/cadrumo/entrypoints/runtime/profile_host.py`)
- `profile_login.py` (`src/cadrumo/entrypoints/runtime/profile_login.py`)
- `session_owner.py` (`src/cadrumo/entrypoints/runtime/session_owner.py`)
- `shutdown.py` (`src/cadrumo/entrypoints/runtime/shutdown.py`)
- `submission_stream.py` (`src/cadrumo/entrypoints/runtime/submission_stream.py`)
- `worker.py` (`src/cadrumo/entrypoints/runtime/worker.py`)
<!-- /preserved:article -->
