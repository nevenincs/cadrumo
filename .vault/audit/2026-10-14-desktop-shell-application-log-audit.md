---
tags:
  - '#audit'
  - '#desktop-shell'
date: '2026-10-14'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:8d5f45b8018e8c43bb4b83fcb5a70507d7ba90b0ca53cb798420b731d601de66'
related:
  - "[[2026-10-04-desktop-shell-adr]]"
---
# `desktop-shell` audit: `User-visible Tauri application log`

## Scope

2026-10-14 source audit prompted by INFO rows containing `stage_started` and `stage_completed`, and the owner's requirement that the application log inside Tauri be rich and complete. Traced native diagnostics, manager supervision, agent hosting, Python structured diagnostics, log ingestion and the React Logs view. Discovery used the current semantic code index and the complete ADR listing. Reviewed desktop-shell and supervisor-contract decisions; the desktop-agent-host record is proposed and is not treated as accepted authority.

This is static source evidence, including inspection of existing tests. No packaged GUI, service registration, running process inventory or live agent gateway was exercised. No product source was changed. Existing unrelated working-tree edits were preserved.

## Findings

### native-severity | high | The adapter collapses internal detail and operational changes into INFO

`native/desktop/src-tauri/src/logs/host.rs:162` maps Failure to ERROR, terminated/nonzero-exit children to WARNING, and every other event to INFO. Consequently admission/environment stage starts and completions, successful helper timings and genuine lifecycle milestones share a level. The default filter is INFO (`native/desktop/frontend/src/shell/records.ts:28`), so the supplied example follows directly from the implementation. Native Event has no severity field (`native/application/src/diagnostics/mod.rs:75`); severity is synthesized by the view adapter, including for persisted manager records. Changing the UI filter alone cannot repair this.

Manager crashes have a separate inconsistency: `native/manager/src/diagnostics.rs:154` projects Exited with no failure, then selects StageCompleted unless another condition applies. The adapter therefore displays a runtime crash as INFO. HostStopped with a nonzero host exit code likewise falls through to INFO. Normal requested child termination is always WARNING without a stop-cause distinction.

### agent-lifecycle | high | Agent readiness, ports and refusals do not become log records

`native/desktop/src-tauri/src/agent/supervisor.rs:327` publishes state changes to the agent status channel, without emitting diagnostics. Its ready handler at line 504 receives gateway port, version and generation, stores the gateway, then publishes Ready. The Logs hub consumes Diagnostics and the Python/manager files, not this status channel (`native/desktop/src-tauri/src/logs/mod.rs:230`). Readiness and gateway endpoint information are therefore absent from the application log at this seam. Refused and stopped protocol signals similarly do not generate service lifecycle records. Preparation/start errors are reduced to ServiceFailed by `.is_err()` at line 464; failures before the runner's own diagnostic calls can lose their typed cause here. The Python controller has a native-refusal warning, but no normal lifecycle logger calls (`src/cadrumo/application/agent_host/controller.py:364`).

### process-identity | high | The log cannot reconstruct a complete current process topology

The agent runner records its launcher as generic Cli (`native/desktop/src-tauri/src/agent/runner.rs:130`); ProcessRole has no agent launcher/gateway/worker roles (`native/application/src/process/status.rs:12`). This obscures which CLI child is the persistent agent service. HostEvents consumes snapshot.events only, although Diagnostics exposes snapshot.processes (`native/desktop/src-tauri/src/logs/host.rs:27`, `native/application/src/diagnostics/mod.rs:376`). The log is bounded history, with no current inventory delivered to reconcile missing starts or process exits. Manager lifecycle rows do carry runtime_pid, so runtime attribution is partially present; it must be preserved alongside emitter identity, rather than replaced by the desktop/manager PID.

### configuration-and-registration | medium | Success records omit the facts needed to explain startup and service management

Environment resolution validates the packaged executable and composes storage/environment, but emits no corresponding typed configuration facts (`native/desktop/src-tauri/src/environment.rs:202`). The view sees broad environment-ready milestones. Optional manager installation is wrapped in the same Manager stage as activation (`native/desktop/src-tauri/src/manager.rs:143`, line 199), without success facts for requested scope, service/login registration, verified registration result or selected ownership mode. The Python context allow-list lacks service, port and binary fields (`src/cadrumo/core/diagnostic_log.py:24`); adding arbitrary logger extras would not make those facts appear in expanded structured context. Endpoint facts must distinguish runtime native IPC from agent loopback HTTP and development/debug listeners; a TCP port must not be invented for a native IPC endpoint. Service registered, process running, endpoint listening and runtime ready are separate observations.

### native-history-loss | high | Native history can disappear without contributing to the visible dropped count

Diagnostics discards its oldest event at 512 (`native/application/src/diagnostics/mod.rs:229`). HostEvents filters by sequence and advances its cursor without reporting sequence gaps (`native/desktop/src-tauri/src/logs/host.rs:27`). The existing full-ring test explicitly expects only 512 of 600 emitted events (`native/desktop/src-tauri/src/logs/host.rs:388`). This loss occurs before Aggregate's otherwise useful dropped accounting. The host is read from memory; its persisted `cadrumo-native.jsonl` is not tailed by the view, which tails Python and manager files only. Opening/reloading the application cannot recover earlier desktop history from that file. A bounded log can be complete about its limits, but must expose omitted history.

### host-sink-health | medium | Host persistence failures have no source-health projection

Diagnostics retains log_failure if appending fails (`native/application/src/diagnostics/mod.rs:224`) and exposes it in Snapshot. HostEvents ignores this field. LogSourceStates contains Python and manager only (`native/desktop/src-tauri/src/logs/record.rs:91`). A desktop append failure can leave the in-memory view apparently healthy while persistence is unavailable. Explicit configure failures already emit Failure events; ongoing append failures need equally visible source state.

### row-presentation | medium | Useful details are available only after expansion and messages remain generic

`native/desktop/frontend/src/components/records/RecordRow.tsx:45` summarizes only stage, startup_phase, phase, outcome and reason_code. Other context is shown as JSON after expansion. Thus helper elapsed times, lifecycle reasons/restart delays and endpoint facts (once supplied) do not form a readable operational narrative in collapsed rows. Text search and copy already include context through recordLine, which is a useful foundation. Generic `stage_completed` messages do not tell the person what service became ready or which application action finished.

### python-timing-severity | medium | Python timing diagnostics also default to INFO

`src/cadrumo/core/diagnostic_log.py:135` stamps monotonic timing and calls diagnostic_event without an explicit level; diagnostic_event defaults to INFO at line 122. Operation-authority timing call sites therefore add internal timing material to INFO independently of the Rust adapter. Python root and file defaults already admit DEBUG (`src/cadrumo/core/config_runtime_fields.py:264`, line 278), so enabling DEBUG globally is not the missing fix.

## Recommendations

1. For native-severity and python-timing-severity, define a shared event/severity policy. Proposed INFO: application launched/ready/stopped, service ready/stopped, ownership changes, terminal/service process lifecycle and meaningful action outcomes. Proposed DEBUG: admission/environment substeps, helper success timings, probes, manifest verification and sanitized configuration selection. WARNING: unexpected exits with recovery, retries, degraded sources and forced shutdown after grace. ERROR: failed requested actions, failed admission/startup and unrecovered cleanup. Preserve actual stop cause and crash classification. Decide explicitly whether severity is producer-owned/versioned or a shared classifier; this audit does not make that schema decision.
2. For agent-lifecycle and process-identity, emit typed state transitions at the owning components, including service role, actual PID, parent/owner relationship, generation, readiness endpoint and bounded reason code. Add authoritative current process/service observations, timestamped and reconciled with history. Do not infer live state from an old start row. The runtime must supply facts about its owned agent tree; the shell must not gain runtime/profile authority to obtain them.
3. For configuration-and-registration, inventory safe configuration fields and publish effective value plus origin/default/override classification at DEBUG. Record verified binary identity/version, package selection and validation outcome. Record manager installation scope/result and installed-versus-GUI supervision changes at INFO. Keep full environment blocks, credentials, bearer tokens, protocol payloads, private paths and terminal content outside logging; sanitized path policy and new native fact schemas require explicit decision coverage.
4. For row-presentation, word meaningful state changes as readable messages and show service/PID, relevant endpoint, outcome and duration inline where applicable. Retain expandable bounded structured details, source/text filters, pause/follow and copying.
5. For native-history-loss and host-sink-health, report source-specific dropped/gap/truncation counters and persistence health. Decide a bounded desktop-history replay strategy with deduplication; preserve separate source/process lifetime identity. Keep existing ring and pacing limits, and make retained-history limits explicit.
6. Verification must cover the actual packaged Tauri view: cold/warm startup, installed manager versus GUI supervision, user/machine registration on disposable hosts, real agent ready/refused/stopped transitions, port conflict, sign-in/profile changes, runtime crash/retry, graceful/forced close, reload, ring overflow and rotation/write failure. Assert correct INFO versus DEBUG content and actual process/endpoint facts through real host delivery. Scan with credential/private-content canaries. Existing browser fixtures or source inspection do not prove packaged integration.


## Remediation 2026-10-14

Authorized by the owner's instruction to implement correct DEBUG/INFO/error levels and an environment override, with INFO as the default. Implemented the native severity classifier, including runtime crashes and failed helper outcomes; successful Python timing events now use DEBUG. The host projects CADRUMO_LOG_LEVEL into the frontend initial/reset filter, with all five standard severities and compatibility for the existing CLI verbosity names. CLI children accept the same standard severities. Diagnostic capture remains available below the selected view filter.

Added typed agent start/ready/refused/retry/stop facts, loopback gateway port and generation, a distinct agent_launcher process role, typed preparation failures, and manager installation scope/outcomes. Expanded row summaries include stop/refusal reasons and helper/retry durations. Native event-ring gaps now produce a WARNING and a dropped count through the real log channel. Host persistence health is a separate source state, recovers after a successful append, and exposes write failures as ERROR records. Updated the backend test runner to read the generated declaration without case-folding its launch vectors. Kept the manager's saturating event-loss counter compatible with the declared Rust floor while avoiding the newer compiler's deprecated fetch_update call.

Verification: native logs suite (49 tests), environment suite (7 tests), real child-process agent-supervisor suite (6 tests), Python diagnostic suite (27 tests), CLI level integration suite (12 tests), browser host-default/reset tests (3 tests), npm check, native Clippy, Python Ruff lint/format, configured Python type checks and import boundaries. The first browser attempt timed out during development-server bootstrap; the retry used the already configured build inputs and passed. Native log tests exercise real Tauri channel delivery, loss accounting and an actual failed/recovered file sink; browser tests exercise the production frontend with a test host. No installed service registration, machine boot/login, or packaged interactive GUI acceptance was performed.

Remaining recommendations from the initial audit: a complete authoritative inventory of all runtime-owned descendant processes, bounded replay of earlier desktop log files, and a broader sanitized binary/configuration catalogue. Those remain distinct from the severity/default override implementation and are not claimed complete. Existing unrelated work and commits by other sessions were preserved.


## Agent diagnostic integration 2026-10-14

The owner explicitly extended scope to all hosted cadrumo-agent diagnostics, including the launcher, gateway and workers. The runtime now forwards schema cadrumo-agent.log/1 records from the contained gateway's stderr and follows gateway/worker rotating logs and worker-autospawn stderr files below that run's owned hosted root. CLI invocation warnings/errors use the agent's logger format. The Cadrumo launcher emits its ready/refused/stopped diagnostics into the shared application log. Stdout remains the private readiness/control protocol. The Logs adapter attributes these records to source cadrumo-agent with agent_launcher, agent_gateway, agent_worker or agent_cli roles and original producer PID, timestamp and severity.

The bridge deduplicates overlapping stream/file copies, frames partial writes, follows file identity across rotation, recognizes truncation and rewritten prefixes, drains final records after tree termination and reports bounded rejection/unreadable/backlog warnings without echoing input. Hosted first-party DEBUG capture is enabled independently of the application's INFO default view; the agent's explicit CADRUMO_AGENT_LOG_LEVEL override can reduce producer output. Safe operational scalars, including ports, elapsed times and trace/span IDs, survive normalization through the existing credential/payload scrubbers. Arbitrary nested tool arguments, private protocol bytes and third-party SDK DEBUG payloads stay outside the plaintext diagnostic feed. Existing logs are baselined before spawning; this change copies new hosted-run diagnostics, not a retroactive import of pre-integration agent history.

Verification: 57 focused Python diagnostic/environment/privacy tests; 16 Windows process/launcher integration tests, including a real gateway process and separate file-only worker PID; 50 native logging tests through the existing Tauri channel; native Clippy. The real process integration verifies original DEBUG and ERROR levels and one record per overlapping output. Packaged interactive GUI acceptance and a provider-backed live agent lane remain unverified. Earlier recommendations about complete live process inventory, installed service registration and replay of desktop-native history remain open. Unrelated concurrent edits were preserved.
