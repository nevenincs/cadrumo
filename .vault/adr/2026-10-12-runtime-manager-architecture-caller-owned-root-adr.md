---
tags:
  - '#adr'
  - '#runtime-manager-architecture'
date: '2026-10-12'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:e089245be78293c2bb553d802716fd3b74bec1655d7860f51e1f5825bb2ca484'
related:
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]"
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
  - "[[2026-10-12-live-agent-evaluation-adr]]"
  - '[[2026-10-04-runtime-manager-architecture-requirements-research]]'
---

# `runtime-manager-architecture` adr: `caller-owned runtime for an explicitly configured storage root` | (**status:** `accepted`)

## Problem Statement

A process outside Cadrumo that selects its own storage root with `CADRUMO_LOCAL_STORAGE_ROOT` cannot get a runtime for that root. The packaged CLI on that root creates a profile, but `config login` is refused with `REFUSED_LOCAL_RUNTIME` because no runtime serves the root. The installed manager supervises only the installed default root and refuses an override (`native/manager/src/supervision/environment.rs:63`, `2026-10-04-runtime-manager-architecture-adr`). The packaged `cadrumo-runtime` can serve any absolute root, but only when the launcher passes `--storage-identity` and `--expected-version` (`src/cadrumo/entrypoints/runtime/arguments.py`). Those values come from Cadrumo internals: an owner/physical-root digest (`src/cadrumo/adapters/local_runtime/windows.py:53`) and the installed distribution version. The cadrumo-agent testbed stopped at exactly this point. It recorded that it must not emulate the runtime protocol, clear the override or import Cadrumo internals to get around it. The runtime also has no public readiness signal and no portable stop for an unsupervised launch.

The operator, 2026-10-12: "Please make the real Cadrumo runtime support the existing CADRUMO_LOCAL_STORAGE_ROOT environment override, alongside CADRUMO_SECRET_STORE_DIR. [...] Provide a supported launch path for an explicitly configured root, with runtime discovery, authentication, data access and MCP all using that root. Preserve isolation from the default installation and allow the caller to manage startup, readiness and shutdown. Do not bypass runtime checks or introduce mocks. [...] Document the launch command for external consumers such as cadrumo-agent."

## Considerations

- Override roots "stay developer-owned and unmanaged" and the manager manages only the canonical default (`2026-10-04-runtime-manager-architecture-adr`). Development and tests may explicitly own runtime lifetimes (`2026-10-03-runtime-without-service-manager-adr`). Unsupervised launches are outside the supervisor contract (`2026-10-04-runtime-manager-architecture-supervisor-contract-adr`).
- Every client resolves its endpoint from `effective_storage_root()` (`src/cadrumo/adapters/local_runtime/runtime_client.py:70`). A runtime that resolves its root the same way serves exactly the endpoint those clients derive.
- The runtime's identity and version arguments guard a supervisor's pinned expectations. A caller that resolved nothing has no pin to compare against. Native peer identity, profile credentials, grants, session binding, custody and worker containment do not depend on those arguments.
- On Windows a caller cannot reliably deliver Ctrl+C to a child it does not share a console with. Closing a pipe works the same way on every platform, and the pipe also closes when the caller dies.
- `CADRUMO_SECRET_STORE_DIR` and the other storage settings already reach workers through `worker_path_environment_names()` (`src/cadrumo/adapters/local_runtime/worker_environment.py`).

## Considered options

- **A caller-owned form of the packaged runtime, `cadrumo-runtime --configured-root`.** Chosen. It resolves the root through the clients' own settings resolution, derives identity and version itself, prints one readiness line, and drains when standard input closes.
- **A CLI command that prints the launch parameters.** Rejected. It adds a runtime administration verb, which `2026-10-03-runtime-without-service-manager-adr` removed. It also leaves readiness and stop to each caller.
- **Let the installed manager supervise override roots.** Rejected. It reverses the manager ruling, and it would contend with an installed manager on a developer host.
- **The desktop host's supervision on an override root.** Rejected for this use. `cadrumo.exe --check-health` is bounded to 60 seconds and needs the desktop build. It is a health check, not a lifetime the caller owns.
- **The debug lifecycle driver.** Rejected. It is gated by `fixture-test-mode`, release builds refuse that feature, and it is not part of the package.

## Constraints

1. `cadrumo-runtime --configured-root` serves only an explicitly configured root: one named by `CADRUMO_LOCAL_STORAGE_ROOT`, or by `CADRUMO_STORAGE_ROOT` in a checkout. It resolves that root with the same settings resolution every client uses.
2. It refuses with `runtime_root_mismatch` (exit 68) when no explicit root is configured, or when the root is, contains or lies inside the installed default root. A refused root is not created.
3. It derives the storage identity and uses its own installed version. `--expected-version` stays available as an optional pin, and a mismatch refuses with exit 69. `--storage-identity` and `--supervised` are refused with this form.
4. Once clients can connect, it writes exactly one JSON line to standard output: `kind` `runtime_ready`, `pid`, `product_version` and `storage_identity`. Nothing else is written to standard output.
5. Its lifetime is the caller's standard input. End of input, or a broken pipe, requests a drain that exits 64 (`SUPERVISOR_STOP`). Ctrl+C and SIGTERM keep their existing exit 65.
6. No runtime check is relaxed: native peer and endpoint ownership, single-owner convergence, login/session admission, profile credentials, grants, encrypted custody and worker containment apply unchanged. No boot record is published, and no login or boot registration is made.
7. The installed manager is unchanged and still manages only the installed default root.

## Implementation

We will add the `--configured-root` form to the runtime entry point: `src/cadrumo/entrypoints/runtime/arguments.py` parses it, `src/cadrumo/entrypoints/runtime/caller_owned.py` resolves and checks the root and owns the readiness line and the standard-input lifetime, and `src/cadrumo/entrypoints/runtime/main.py` passes the derived values through the existing owner path. Integration tests drive the installed launcher over real IPC, including the refusals (`src/cadrumo/entrypoints/runtime/tests/test_caller_owned_runtime.py`). The launch command is documented for external consumers in `docs/how-to/connect-an-agent.md`.

Hypotheses that may change within the constraints: the flag's name, and the readiness line's field set beyond the four named fields.

## Rationale

The runtime that serves the root is the only component that can derive the root's identity without importing internals, and it already resolves storage the way the clients do. Moving the derivation into the runtime removes the internal dependency without adding a management verb. It leaves the manager ruling and the supervisor contract untouched. A pipe-bound lifetime gives the caller startup, readiness and shutdown control on every platform. It also guarantees that the runtime does not outlive the caller that owns the root.

## Consequences

- An external caller can run the packaged runtime on a disposable root, then authenticate, operate and connect MCP through the ordinary public clients with the same environment.
- A caller that launches with standard input on the null device gets an immediate stop. That is documented, and it is the price of a lifetime that cannot be leaked.
- Exit 64 now also means that the owning caller closed standard input.
- Strict login/session admission still applies. A caller on a host whose logon the native credential store refuses (for example error 1312 under SSH) can serve the root, but cannot rely on stored sign-in receipts there.
- Accepted 2026-10-12 on the operator's explicit request quoted above. The flag name and the line and pipe protocol are this record's choices within that request. Acceptance records the decision; the verification evidence is reported separately.
