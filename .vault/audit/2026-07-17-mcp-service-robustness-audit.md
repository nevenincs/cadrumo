---
tags:
  - '#audit'
  - '#mcp-service-robustness'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - '[[2026-07-17-mcp-service-robustness-research]]'
  - '[[2026-07-15-distribution-installation-readiness-plan]]'
---

# `mcp-service-robustness` audit: `execute meta-tool event-loop blocking fix`

## Scope

Reviewed the fix for the critical serving-path defect recorded as F1 in the
feature research: the `execute` meta-tool dispatched its gated subprocess
runner synchronously inside the async `call_tool` handler, freezing the event
loop for the full timeout tier on the default CORE surface. The review covered
the shared off-loop wrapper introduced in `_server.py`, the regression module
`test_server_loop_responsiveness.py`, and the verification sequence.

## Findings

### execute-loop-blocking | critical | Default-surface tool calls froze the MCP session for the full call

Confirmed at pre-fix HEAD: the `execute` branch called the subprocess runner on
the event-loop thread while the direct per-verb path used an off-thread wrapper
with a progress heartbeat. Fixed in commit `2dd7d1d1a0` by generalizing the
wrapper (`_run_offloop_with_progress`) and routing both paths through it; the
gate suite still runs unchanged and the shared session state it touches is
limited to GIL-atomic list-append and boolean-flag operations, so the worker
thread introduces no new race class beyond the interleaving that already
existed between concurrent direct calls.

Verification was anti-tautological: a first done-state assertion was proven
tautological (it passed against the deliberately re-blocked dispatch because
client-task completion is scheduling-deferred) and was replaced with a
completion-gap invariant — a mid-call `tools/list` must complete at least one
second before the subprocess call completes. The rewritten test failed against
the re-blocked dispatch (20.1 s run, gap below threshold) and passed against
the fix for both the `execute` path and the direct per-verb path. Focused Ruff,
`ruff format --check`, and `ty check` passed on both touched files. The full
MCP entrypoint suite passed except two pre-existing `test_risk_table_parity`
failures naming the `config.reset` command key, which belong to the in-flight
config-reset peer campaign (uncommitted peer WIP in `_dispatch.py` and
`_input_schema.py`) and are untouched by this change.

## Recommendations

Remaining remediation queue, in order: decide the per-call latency architecture
(research F2 warm worker or registry cache, with the F3 concurrency cap and F4
MCPB `uv run` startup cost in the same decision) through an ADR before any
implementation; then the F5 hardening tail (narrow the broad progress-send
suppression, add a `process.kill()` fallback when `taskkill` is unresolvable,
and re-evaluate the READ tier ceiling against the measured cold-start floor).
Re-run the Cowork/Desktop client evidence lane after any of these land so the
distribution-installation-readiness client rows observe the improved serving
behavior.
