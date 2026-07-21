---
tags:
  - '#research'
  - '#mcp-service-robustness'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - '[[2026-07-17-mcp-service-robustness-audit]]'
  - '[[2026-07-15-distribution-installation-readiness-plan]]'
---

# `mcp-service-robustness` research: `MCP serving-path robustness defects`

Operator-reported Claude client symptoms against the Cadrumo MCP surface — lags,
drops, hangs, and flow issues, most visible on the Cowork/Desktop MCPB surface —
were investigated with a full read of the server core (`_server.py`), the
supervised subprocess runtime (`_call_runtime.py`), the MCPB bundle launcher
(`packaging/mcpb`), and the test surface. The findings ground the fix landed
under this feature and the remaining remediation queue.

## Findings

### F1 (critical, FIXED): `execute` meta-tool blocked the asyncio event loop

The `execute` branch of the server's `call_tool` handler dispatched the gated
subprocess runner (`_gated_subprocess_run` ending in `Popen.communicate`)
synchronously inside the async handler. For the whole call duration (timeout
tiers 45/180/420 s) the event loop was frozen: no ping handling, no progress
heartbeats, no concurrent calls, no cancellation. The direct per-verb path
already had the correct off-thread wrapper with a 5-second progress heartbeat;
the meta path never received parity. CORE is the default advertised surface, so
most verbs on a default client session route through `execute` — the default
Cowork/Desktop configuration ran the blocking path for essentially all tax
work. This matches the reported hang/drop symptoms exactly and was documented
nowhere in prior audits. Fixed by routing the meta-execute call through a
generalized shared off-loop wrapper (`_run_offloop_with_progress`) used by both
paths; proven by a red-without/green-with completion-gap regression
(`test_server_loop_responsiveness.py`). Commit `2dd7d1d1a0`.

### F2 (high, open): cold subprocess plus full registry load on every call

Every tool call spawns a fresh `aeat` CLI process; there is no warm worker and
no cross-call registry cache, so each call pays interpreter start, imports, and
registry TOML compilation — a multi-second floor per call on Windows,
independent of F1. This is the dominant cause of per-call lag. Candidate
remedies (warm worker process, persistent registry cache keyed by the tree
fingerprint, or a batch channel) change the process architecture and need an
ADR before implementation.

### F3 (medium, open): no concurrency cap on subprocess spawn

Direct calls offload to the anyio default thread pool (40 threads); N
concurrent calls can spawn N full CLI processes with no semaphore. A burst
thrashes CPU/RAM on the host. Remedy belongs with the F2 decision.

### F4 (medium, open): MCPB session start runs `uv run` resolution every launch

The MCPB manifest launches `uv run --directory ${__dirname} src/server.py`;
each client session pays a UV resolve/sync check before the server accepts the
initialize handshake, adding connect latency and occasional startup stalls on
the Desktop/Cowork surface. Candidate remedy: pre-provisioned environment with
a direct interpreter launch after first provision.

### F5 (low, open): hardening tail

`contextlib.suppress(Exception)` around the progress-notification and
tools-list-changed sends can hide a genuinely broken write stream; the Windows
process-tree kill silently no-ops when `taskkill` is not resolvable (stranding
a hung browser child) instead of falling back to `process.kill()`; and the
READ tier's 45-second ceiling sits close to the cold-start floor of F2 on slow
machines, risking false timeouts on a first read.

### Stdout hygiene: clean

No stray stdout writers exist in the package; child output is piped, telemetry
writes to files, `stdin` is `DEVNULL`-isolated, and encoding is explicit — the
JSON-RPC stream itself is not at risk from child output.

### Empirical latency decomposition (installed cohort, Windows workstation, 2026-07-17)

Measured against the installed v0.2.1 cohort CLI with an isolated fresh state
root, one step per subprocess exactly as the MCP serving path dispatches:
`--version` 1.96 s (interpreter plus imports); `profile create` 4.3 s;
`modelo work create` **49.6 s on first touch of a fresh state**, 10.0-10.2 s on
every subsequent create in the same state; `modelo work calculate` 11.9-12.2 s
per call; `modelo list` 5.4 s warm. In-process profiling attributes the
recurring cost: full-registry validation (`validate_registry`) is ~5.8 s and
runs once per process — legal-catalogue corpus verification (~1.9 s),
catalogue-wide revision-section validation across all modelos (~2.5 s), and a
semantic-role typo scan (~1.1 s) dominate — while a second snapshot in the
same process costs 0.000 s. The warm per-call floor is therefore roughly 2 s
interpreter + 6 s registry re-validation + 2 s storage/engine, re-paid on
every tool call because each call is a fresh process (F2). The ~40 s
first-touch cliff inside `work create` occurs between SQL-engine creation and
the work-unit catalogue write (a silent log gap) and is a one-time per-state
computation, not registry validation; it is what pushed the real Claude
Desktop client past its 60 s request timeout in the S39 acceptance run. The
functional result is correct in every lane (`DP200014:00562 == 23000.00`
grounded); the latency is the defect. Remedy shape for the F2 ADR: persist the
already-fingerprinted registry validation verdict across processes (the tree
fingerprint is computed in under 1 s), and name the first-touch computation
with a targeted trace before deciding its cache or deferral.

### Test-surface gap

Before this feature nothing exercised loop responsiveness, slow calls, or
concurrency; the new completion-gap regression covers F1 for both dispatch
paths. F2/F3/F4 remain unexercised pending their ADR.
