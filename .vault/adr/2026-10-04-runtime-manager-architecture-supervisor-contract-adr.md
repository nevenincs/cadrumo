---
tags:
  - '#adr'
  - '#runtime-manager-architecture'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:1909a4297942f215019e762c283e94f428e302c9df0dad7d8b08cc4f39c2c8a3'
related:
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-requirements-research]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
  - "[[2026-10-03-runtime-without-service-manager-scope-removal-audit]]"
---

# `runtime-manager-architecture` adr: `Runtime supervisor contract` | (**status:** `accepted`)

## Problem Statement

`2026-10-04-runtime-manager-architecture-adr` makes a per-user manager the only product component that controls the runtime's lifecycle. Today the runtime gives a supervisor almost nothing to work with:

- no readiness signal
- one exit code for every refusal and for the watchdog
- no hang detection
- no session-end path that fits the roughly 5 s budget Windows and logind allow
- no identity record that lets a supervisor recognise a runtime it did not launch

The supervisor must not widen authority. The MCP adapter "must not stop a shared runtime" (`2026-09-26-mcp-purpose-authentication-adr`). This record decides what the runtime itself offers a supervisor. Evidence: `2026-10-04-runtime-manager-architecture-requirements-research`, including its review-found runtime facts.

## Considerations

- Transport admission checks only the account and process liveness. It does not check the session or the kind of client. A transport verb therefore cannot tell the manager from an agent.
- The installed host runs Python isolated in one process with signal handlers installed. SIGINT already maps to the drain.
  - Console Ctrl+C on Windows and SIGTERM on POSIX reach that path across versions.
  - The ignore-Ctrl+C state is inherited.
  - The KDF child and the browser installer share the runtime's console.
- The version handshake closes mismatched peers before any request.
- The standard streams are inheritable. A stray write, or a write after the reader has died, can corrupt the channel or change the exit code.
- Today a witness-loss self-stop exits `0`, indistinguishable from a clean stop (`profile_connections.py:127`, `main.py:171`).
- Operation leases last 10 minutes. Releasing a lease while a worker still runs would give an effect a second owner.
- The verified transport has one owner. A Rust copy is excluded (`2026-10-03-application-packaging-adr`).

## Considered options

- **Supervisor channel on the launched process's standard streams, plus OS stop signals and a non-private boot record.** Chosen. Cadrumo's interfaces cannot reach it, it adds no transport surface, it does not couple versions, and it needs no Rust transport client.
- **Supervisor verbs on the verified transport, restricted by peer image.** Rejected. It needs a Rust transport, it cannot reach a runtime of another version, and it reopens the endpoint that the 2026-10-03 removal closed.
- **Inherited dedicated handle or descriptor.** Equivalent authority with more launch mechanics on each platform. It is the fallback, and it is the means of passing the channel to a successor manager if handoff ever needs it.
- **Exit codes and liveness only.** Rejected. There would be no hang detection and no bounded session-end settle.

## Constraints

**Scope.** All of this applies only while the runtime runs with `--supervised`. Unsupervised development and test launches are unchanged.

**Carriers.**
- The contract is carried only by:
  - the launching process's standard streams
  - OS stop signals
  - the boot record
- No supervisor, stop or status verb is added to the transport.
- No Python client function exists for it.

**Stream hygiene.**
- At startup the runtime moves the protocol input and output to private, non-inheritable handles.
- It points fd 0, fd 1 and fd 2 at the null device and replaces `sys.stdout` and `sys.stderr`. Native writes therefore never reach a log unredacted.
- It routes `sys.excepthook`, `threading.excepthook`, `sys.unraisablehook` and warnings through redacted logging.
- Protocol writes:
  - are line-delimited, with a closed grammar and bounded size
  - run off the serving threads
  - never block admission or logging
  - disable the channel when the pipe breaks
- No exit code may result from a stream failure.
- The manager never receives raw diagnostic text, only bounded reason codes.
- End-of-file on the protocol input means the supervisor is gone. The runtime keeps serving and stops sending heartbeats.

**Stop signals.**
- In every version, POSIX SIGINT and SIGTERM, and Windows console Ctrl+C, map to the graceful drain. This is a promise across versions. Windows has no catchable SIGTERM: `TerminateProcess` and job termination are forced kills, not stops.
- The runtime calls `SetConsoleCtrlHandler(NULL, FALSE)` at startup.
- It gives each non-worker child its own console, so that a stop reaches the runtime alone.
- A Ctrl+C that arrives before the handlers are installed cannot be guaranteed a reason code. The manager maps `STATUS_CONTROL_C_EXIT`, and a `0` exit following a stop it sent, to a signal stop. A `0` exit the manager did not request is an unexpected exit and is restarted with backoff.

**Boot record.**
- A supervised runtime publishes a non-private boot record under its storage root's `.runtime/`, beside `installation.json`.
- Contents: boot id, pid, process creation time, version, versioned package directory and admission policy (`native` or `development`).
- It is written and read with the hardened custody local-record primitives already used there: bounded size, duplicate-key rejection and atomic publication.
- It is replaced on each boot and removed on a clean exit.
- It is an identity claim used for adoption, not authority. Its location is registered in the storage taxonomy.

**Session-end settle.** `session-end` runs in this order:
1. Fence admissions.
2. Terminate the runtime's worker job and confirm the termination.
3. Record `ORPHANED` or `UNKNOWN` and release only the leases of confirmed-terminated work.
4. Exit.

Unconfirmed work keeps its lease until normal expiry. The settle must fit inside the platform's session-end budget (*hypothesis*: 3 s).

**Exit reasons.**
- The table is owned by `src/cadrumo/application/runtime/contracts.py` and projected to Rust through the contract generator.
- It reserves Python's `1`, argparse's `2`, CPython's `120`, the native host's `120`-`124`, `STATUS_CONTROL_C_EXIT` and other NTSTATUS crash codes, and POSIX signal exits.
- CPython's own configuration and argv paths can exit with `1` or `2` before the runtime runs. The supervisor reads those as launch failures, never as runtime-defined reasons.

**Elevation.** A supervised runtime refuses a full UAC-elevated token (`TokenElevationTypeFull`). Accounts with UAC disabled are not refused. The packaged binary is `asInvoker`, so this applies only when its parent is already elevated.

**Readiness.** Client readiness remains the authenticated handshake. A `ready` line is the launched process's own assertion and never stands in for client readiness.

## Implementation

We will add a supervised mode to the runtime with a small line protocol and a boot record. Field names and grammar are *hypotheses* within the constraints.

- **Runtime to supervisor:**
  - `ready`: boot id, pid, version, storage identity and admission policy, sent after the endpoint is owned and the boot record is published.
  - `heartbeat`, in reply to `ping`: sequence, accept-loop tick age, connected-frontend count and in-flight operation count.
  - `stopping`: reason code.
- **Supervisor to runtime:**
- `ping`
- `stop`: the normal drain
- `stop-if-idle`: fences admissions, then stops only if no operation is in flight; otherwise admissions reopen and the reply says busy
- `session-end`
- **Exit reasons**, numbered by the contract owner:
  - supervisor stop
  - signal stop
  - session-end settle
  - owner busy
  - root mismatch
  - version mismatch
  - login-witness loss
  - drain watchdog
  - elevated token refused
  - unexpected failure

**Follow-on runtime decisions.** These are named, not made:
- Should an UNKNOWN login inventory stop an idle runtime? An idle-runtime soak test should measure how often false witness loss happens.
- Should the installed package image refuse the development session override and authority-root overrides? That would make the boot record's policy field verifiable.
- Should elevation refusal be unconditional for the installed image?
- Confirm that a runtime in an account with no profile creates nothing beyond `.runtime/` and `logs/`.

## Rationale

Cadrumo's interfaces cannot reach the standard-stream channel. Its authority comes from process ancestry, not transport admission, and transport admission cannot tell a manager from an agent. That keeps the accepted rule that clients never stop a shared runtime.

OS signals give the manager a stop that works on adopted runtimes and older versions. The boot record lets the manager recognise its own runtimes by identity. The ordered settle preserves single ownership of effects within the session-end budget. Distinct exit reasons and a heartbeat are the minimum needed to restart after a crash or hang, and to stand down on configuration refusals.

## Consequences

**Benefits:**
- The manager learns readiness and detects hangs.
- It stops the runtime gracefully, settles at session end and tells exit causes apart.
- It recognises its own runtimes.
- No new transport authority exists.

**Accepted costs:**
- A `--supervised` mode with stream and hook rewiring, a new settle step in the supervisor, a boot record, an exit-code table, and tests for each.
- Same-account native code can still signal a stop. The manager restarts any stop it did not initiate.
- An adopted runtime is supervised by process handle and signals only, without hang detection, until its next restart.
- Interrupted work at session end may stay leased for up to 10 minutes.

**Amendment owned by this record**, once accepted, to `2026-09-26-mcp-purpose-authentication-adr`:
- Its exclusion of "start/stop/status administration endpoints" holds for the transport, "except the supervisor contract carried by the launching process's standard streams, OS stop signals and the non-private boot record, defined in `2026-10-04-runtime-manager-architecture-supervisor-contract-adr`".
- Its launch-policy pointers redirect to `2026-10-04-runtime-manager-architecture-adr`. These are the purpose line, the runtime ownership paragraph, the end of the local transport section, and the restart and upgrade deferral.
- The rule that the adapter must not stop the runtime is unchanged.

**Reconsider if:**
- stream rewiring breaks a dependency that needs fd 1 or fd 2
- the settle cannot fit the platform budget
- the follow-on decisions remove the need for the boot record's policy field or for witness-loss restarts
