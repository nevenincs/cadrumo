---
tags:
  - "#adr"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: Filing Submission Engine — ADR
related:
  - "[[2026-04-12-submission-engine-research]]"
  - "[[2026-04-12-deadline-engine-adr]]"
issue: wgergely/aeat#42
---

# adr: filing submission engine

## context

The project's north star is fully automated end-to-end tax filing for
a Spanish autónomo. The submission engine is the final orchestration
layer that drives a browser session against AEAT's portal, fills
casilla-keyed form values, and records a typed audit trail. It runs
after the filing draft engine (#39) produces a ready-to-submit draft
and after the deadline engine (#38) confirms the window is open.

## decisions

### D1: dry-run is the default everywhere

`SubmissionEngine.submit_draft(draft)` defaults to `dry_run=True`. The
CLI exposes `preflight`, `dry-run`, and `submit` as distinct
subcommands — `submit` is the only way to transition to live mode.
**Rationale:** a wrong live submission is irreversible; a wrong
dry-run costs nothing. Defaults must fail safe.

### D2: live submission is double-gated

To submit live, two independent gates must be open:

1. `override_confirmation=True` explicit parameter (CLI passes this
   only when `--i-understand-this-is-real` is present).
2. `settings.aeat_submission_require_human_confirmation=True` in
   `Settings` (default: True — it GATES, it does not PERMIT).

The first is a per-call explicit act by the caller; the second is a
system-wide safety flag the user configures. When the safety flag is
False, the call is **still** rejected — the safety flag is a
belt-and-braces existence check, not a permit. The CLI docstring
documents this explicitly. (This is intentionally conservative; we
may loosen it once the engine has run in anger.)

### D3: any ERROR-severity finding blocks submission

`Preflight` inspects `draft.findings` and raises
`SubmissionPreflightError` if any entry has `severity == ERROR`. WARN
and INFO are advisory and do not block. This puts the escalation
decision in the draft engine (#39) where it belongs.

### D4: Submitter is an abc.ABC with coroutine methods

`Submitter` exposes two `@abstractmethod` coroutines: `dry_run` and
`submit`. Each takes the same keyword-only parameters and returns a
`SubmissionAttempt` (dry-run) or `(SubmissionAttempt, Justificante |
None)` (submit). **Rationale:** one concrete class per modelo, each
encoding its portal walk. This is a simple, extensible pattern —
plugin-y abstractions are premature for v1.

### D5: dependencies injected via Protocols, never hard-imports

The engine takes every sibling dependency as a Protocol instance in
its constructor. This is the same pattern from `aeat.domain.deadlines` and it
makes rebase against in-flight siblings a single-file diff
(`_protocols.py` → `aeat.<sibling>`). See
`[[2026-04-12-submission-engine-research]]` §in-flight-dependencies.

### D6: BrowserSessionLike narrow protocol, real test doubles

The submitter takes `BrowserSessionLike`, a Protocol listing only the
methods it uses. The concrete `aeat.adapters.outbound.aeat.browser.BrowserSession` conforms
structurally. Unit tests pass a deterministic Python class that
records every call into a list; this is explicitly **not** a mock —
it is a Protocol implementation written by hand, per the project rule.

### D7: persistence is flat JSON under `aeat_submissions_dir`

`SubmittedFiling` is serialised with `model_dump_json(indent=2)` to
`aeat_submissions_dir / f"{submission_id}.json"`. No database
integration in v1 — that hooks into #10 storage later.

## consequences

- Rebase against #6 / #7 / #8 / #23 / #39 / #44 is mechanical:
  swap each Protocol stub for the real import.
- Dry-run-by-default protects the user against CLI fat-fingering but
  means every live filing is a two-step ritual; this is acceptable.
- The `SubmissionEngine.submit_draft` behaviour is fully deterministic
  in dry-run mode (no real browser state is mutated) — tests can pass
  a recording Protocol implementation and observe the full call
  sequence.

## alternatives considered

- **Plugin entry-points for submitters.** Rejected as premature. A
  `Mapping[str, Submitter]` injected into the engine constructor
  keeps it testable and explicit.
- **Storing attempts in SQLite via #10.** Rejected for v1 — the flat
  JSON files are the simplest thing that audits cleanly. Migration to
  #10 is a separate feature.
- **Single gate on live submission.** Rejected. The belt-and-braces
  double gate is cheap and the failure mode of a wrong live filing is
  too expensive to single-gate.
