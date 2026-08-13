---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:d970b3f89f44a6974af63c828ca476c54f56113b3dd6dff46e31b56f04b8ac7b'
step_id: 'S37'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Measure the real overview-status notice-action path, inventory each invocation's reconciliation and MCP descriptor construction, and set a regression bound from the sequence sandbox.

## Scope

- `src/cadrumo/entrypoints/cli/_common.py`
- `src/cadrumo/entrypoints/cli/_overview_rendering.py`
- `src/cadrumo/entrypoints/cli/tests`
- `dev/docs/sequences/tests`

## Description

- Ground the overview notice projection in `_overview_rendering.py`, the successful Notice action bridge in `_common.py`, and the descriptor projection in `_tools.py`.
- Record the authoritative Sol measurement: one complete live-surface reconciliation and MCP descriptor inventory takes 9.495 CPU seconds across about 309 reconciled leaves.
- Record that one `overview status` invocation emits about 66 action-bearing notices, so the present per-notice rebuild predicts at least 626.670 CPU seconds before ordinary command work.
- Confirm the current loaded registry boundary with `aeat --format json app registry verify`: 73 modelos and a successful authority load in 38.493 wall seconds.
- Bound one additional public command to sixty seconds. `aeat --format json app modelo work list` returned its typed absent-session refusal in 11.509 wall seconds; it is evidence of command overhead and the session boundary, not a healthy calculation analogue.
- Map the fourteen affected generated sequences to the five owning pages: first-quarterly-filing, irpf-lifecycle, modelo-130, quickstart, and review-calculation-values.

## Outcome

The P03 baseline is complete without source instrumentation. The expensive work is canonical and singular: each successful Notice action reaches `resolve_notice_action`, which currently calls `_current_operator_surface_reconciliation`; its MCP-exposure projection calls `build_tool_descriptors`. Rebuilding that 309-leaf inventory for approximately 66 actions gives the observed lower-bound prediction of 10.445 CPU minutes, which explains the canonical isolated check exceeding its 180-second bound.

S38 acceptance is exact: one full reconciliation and descriptor inventory per `overview status` invocation, or one explicit invocation-scoped batch with equivalent lifetime; never process-global cache. S39 must prove every action-bearing notice retains the same typed action id, command key, CLI path, argument bindings, provenance, envelope status, and text output as the baseline. Its CPU ceiling must be derived in the canonical performance helper as `(9.495 CPU seconds + measured healthy overview command overhead) * 1.64`; a raw wall-clock ceiling is not an acceptance criterion. S40 must make page, sequence id, and frame visible before the existing 180-second runner bound. S41 must complete each affected isolated sequence and its five page-coherence gates inside their canonical 180-second bounded runs, with no golden refresh unless the CLI-owned output has genuinely changed.

## Notes

The registry is peer-dirty but was load-stable for this snapshot: `legal/censo.toml` and `legal/irpf-retencion-administradores.toml` remain outside this Step's ownership. The successful registry verify is the executable stability proof; clean Git status is not required and was not claimed.

An earlier attempted long cProfile/tracemalloc measurement was abandoned under the later bounded-run instruction and is not evidence for this record. No production code, tests, sequences, or goldens changed in S37.
