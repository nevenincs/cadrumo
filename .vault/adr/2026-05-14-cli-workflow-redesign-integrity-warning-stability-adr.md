---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `integrity-warning stability` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`.

## Problem Statement

The `integrity-warning: unreadable_rows=N` count drifts between sessions
on the same install without any operator action:

```text
session 1: integrity-warning: unreadable_rows=345
operator runs `aeat config repair quarantine --yes`
session 1: integrity-warning: unreadable_rows=0
session 2: integrity-warning: unreadable_rows=15
session 2: integrity-warning: unreadable_rows=0
session 3: warnings on a different table count again
```

The integrity score should reflect a stable property of stored data
(AES-256-GCM tag verification across the secure-objects table). Drift
under normal use implies one of: schema-shape changes between sessions,
wallclock or environment input mixed into the integrity computation,
non-deterministic master-key handling, or a probe that re-classifies
rows it has not yet seen as `unreadable` until the next pass.

## Hypothesis (to confirm or falsify)

The leading hypothesis is concurrent-writer contention: multiple agent
processes (parallel Codex/Claude/Gemini sessions, parallel test runners,
or an interactive shell racing a background service) hold overlapping
write handles to the same SQLite-backed secure-objects table during a
single wallclock window. The phantom `unreadable_rows` count is then a
read observing a row mid-write, or a row whose AES-256-GCM tag was
written by one process before the byte payload was finalised by another.
This is a HYPOTHESIS, not a pre-committed root cause; the probes below
MUST confirm or falsify it before any fix is shaped. If the probes
falsify concurrent-writer contention, the determinism and
schema-stability data they capture narrow the search to the actual
cause (master-key derivation drift, scan-pass classification, or schema
mutation under normal use). The probes MUST record writer PIDs and
ISO-8601 timestamps for every observed write so a concurrent-writer
pattern is detectable in the captured triples.

## Considerations

The `aeat config repair integrity` surface and the historical
`aeat config doctor` row both consume the same backend integrity scan.
Whatever the root cause, it sits below the CLI boundary and is shared by
both surfaces. The audit cannot pin the cause to a single subsystem
without instrumentation. This ADR captures the finding, declares the
target stability contract, and mandates an investigation step.

## Constraints

- Integrity-warning output is observability, not state mutation. The
  CLI surface does not change as a result of this ADR; only the
  underlying scan and the row's stability properties change.
- No suppression flag is introduced. Hiding the warning to mask drift is
  rejected.
- The investigation MUST distinguish "rows are actually flipping
  between readable and unreadable" from "the scan classifies rows
  non-deterministically".

## Implementation

The investigation is two steps. Both must complete before the
target-state acceptance criteria can be asserted in CI.

1. **Determinism probe.** A backend probe script runs the integrity
   scan N times in a row on the same install, without any mutation
   between runs, and records `(row_namespace, row_key,
   integrity_status, observing_pid, observed_at_iso8601)` tuples for
   each run. The probe is committed under the project's existing
   scripts/probes location. The probe either confirms determinism
   (every run produces identical observations) or pinpoints the rows
   that flip, capturing their on-disk byte length, master-key
   derivation inputs, the PID and ISO-8601 timestamp of every observed
   write that touched the row inside the window, and the PIDs of any
   peer processes holding write handles concurrently. The PID +
   timestamp axis is required so the concurrent-writer hypothesis is
   confirmable or falsifiable from the captured data alone.

2. **Schema-stability check.** A second probe records the secure-objects
   table schema (column types, indexes, encryption parameters) at
   process start and at process exit. Drift between the two snapshots
   indicates schema mutation during normal use; identity indicates the
   scan itself is the source of drift.

The findings of both probes are appended to this ADR or, if extensive,
captured in a follow-up reference document linked from this ADR's
`related` frontmatter.

Once the root cause is identified, the target stability contract is:

- The integrity scan is pure: given the same secure-objects table state
  and the same master key, it produces the same `unreadable_rows` set
  across every run.
- The `integrity-warning` row in `aeat config repair`'s composite report
  prints the actual count exactly; it does not paraphrase, threshold,
  or smooth between runs.
- The scan does NOT mix wallclock, process pid, or any other ambient
  input into its computation.
- The `aeat config repair quarantine --yes` mutation is the only legal
  path that changes the `unreadable_rows` set; if the count changes
  without that mutation having run, the underlying defect is open.

## Rationale

Integrity is the foundation of every other "is my data safe?" promise
the CLI surfaces. A drifting integrity count is worse than a stable
high count: it makes the operator distrust the diagnostic surface
itself. Promoting stability into a typed contract — and gating it on
a determinism probe — keeps the diagnostic surface trustworthy.

The two-probe approach exists because the audit could not pin the root
cause from outside the CLI boundary. The probes are inside the existing
scripts surface, not new CLI verbs, in keeping with the two-root
invariant.

## Consequences

- The investigation runs as a discrete step in the test-user audit
  closure wave (see the apex plan delta).
- Until the probes complete and the root cause is fixed, the
  `integrity-warning` row remains correct in shape (it reports what the
  scan returns) but its stability is provisionally not guaranteed. The
  CLI does not suppress the row in the meantime.
- No CLI surface changes ship with this ADR's acceptance.
