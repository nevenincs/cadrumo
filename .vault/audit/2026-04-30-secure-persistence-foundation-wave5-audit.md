---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave5-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-wave5-research]]"
  - "[[2026-04-30-secure-persistence-foundation-audit]]"
---



# `secure-persistence-foundation` wave-5 audit gate | (**status:** `passed`)

## Summary

Wave 5 closes the three carry-forwards from the wave-4 audit gate:

- Phase 1 — Run-trace redaction: `JsonlRunSink.emit` now routes every
  event through `redact_structured` against the DIAGNOSTIC-class
  default rule set before serialisation. Tests confirm no plaintext
  NIF, URL path, or bearer-shaped token lands in `events.jsonl`.
- Phase 2 — Engine persist migration: `SubmissionEngine._persist`
  routes through `SubmissionRepository.save`;
  `_persist_amendment_result` routes through
  `FilingAmendmentRepository.save`. Both at AUDIT class. The legacy
  plaintext `<id>.json` path is no longer written.
- Phase 3 — Engine audit-sink migration + deprecation wrapper: the
  three engine `append_live_submit_audit` call sites now route through
  `GovernedLiveSubmitAuditSink.append`. Engine knob renamed
  `live_submit_audit_log_path` → `live_submit_audit_dir`. Legacy
  `aeat.adapters.outbound.aeat.export._audit.append_live_submit_audit` becomes a
  `DeprecationWarning` wrapper that preserves on-disk behaviour for
  third-party callers but points them at the governed sink.

Test footprint: 6 new test functions (5 sink-redaction + 1 deprecation-
warning), 4 fixture migrations to envelope paths, 1 deferred-import
fix. Full unit-suite regression: 3775 passed / 18 skipped / 21
deselected.

## Findings

### CARRY-FORWARDS — CLOSED

All three wave-4 carry-forwards are now closed:

- Run-trace JSONL no longer carries plaintext NIF, URL paths, or
  bearer tokens — confirmed by 5 dedicated redaction-discipline tests
  against form-fill, navigation, and error events.
- Engine persist path is governance-gated: every `submit_draft` and
  `submit_amendment` writes through the wave-4 repositories; the
  on-disk envelope carries the AUDIT classification gate.
- Engine audit-sink emissions go through the governed sink; the
  legacy log path is no longer reachable from inside the project.

### REGRESSION INTRODUCED + FIXED — json-pipe-safety

Wave-5 phase-1 and phase-2 introduced top-level `from ..storage
import ...` statements at module scope in `observability/_sink.py` and
`submission/_engine.py`. The `aeat.adapters.persistence.storage` package eagerly imports
Alembic plugin discovery, which logs INFO lines on stderr at import
time. The CLI json-pipe-safety contract requires stderr to remain
empty when ``--json`` output is in flight.

The wave-3 audit gate had already addressed this for the financial+
secrets CLIs by deferring storage imports. Wave-5 regressed it via
the new top-level imports.

Fixed in commit `ce88225` (deferred-import patch):

- `observability/_sink.py` — `_diagnostic_rules()` resolves the rule
  set lazily on first emit; `redact_structured` is imported inside
  the emit method body.
- `submission/_engine.py` — `SubmissionRepository`,
  `FilingAmendmentRepository`, and `GovernedLiveSubmitAuditSink`
  imports moved out of module scope into the per-method helpers.

Confirmed clean by re-running the 7 `test_json_pipe_safety` tests.
Captured here so the wave-6 phase-0 sweep can verify the same
discipline is held.

### Cross-cutting design checks — PASS

- Pydantic v2 strict frozen at every boundary (every public model
  carries `ConfigDict(strict=True, frozen=True, extra="forbid")`).
- Per-record exclusive_file_lock on every save/migration step inherited
  from wave 4.
- DIAGNOSTIC-class redaction rule set covers form-fill values, URL
  paths, and bearer-shape tokens — same discipline as the AUDIT-class
  governed sink, with a separate rule registry so per-class policy
  edits do not cross-contaminate.
- Legacy `_audit.py` writer preserved as a deprecation wrapper —
  third-party callers continue to work; new callers see a clear
  warning pointing them at `GovernedLiveSubmitAuditSink`.
- Engine knob rename (`live_submit_audit_log_path` →
  `live_submit_audit_dir`) is a deliberate breaking change at the
  engine constructor surface; the only affected caller in the codebase
  (`test_safety_helpers.py`) was updated in the same commit.

### No new HIGH/MEDIUM findings

This pass surfaced no new HIGH or MEDIUM findings beyond the
self-introduced + self-resolved json-pipe-safety regression. All
load-bearing claims of the wave-5 ADR are verified by tests on real
on-disk persistence.

## Wave-6 inputs

The following are *carried forward* into wave 6 (caches and corpora)
rather than blocking wave 5:

- The legacy `aeat.adapters.outbound.aeat.export._audit` writer is still in the public
  surface as a deprecation wrapper. A future wave excises it cleanly
  after operators have migrated their callers.
- The transport-level `AmendmentSubmissionResult.dry_run` and
  `submitted_at` fields are dropped from on-disk persistence; the
  inner `FilingAmendment` is the load-bearing audit record. If a
  future caller needs the wrapper fields, they can be added back as
  a dedicated repository.
- Wave-5 phase-3 retained the Alembic INFO leak symptom check as a
  permanent regression test (`test_json_pipe_safety`); future waves
  must keep storage imports deferred.

## Decision

Wave 5 audit gate: **PASSED**. Wave 6 may proceed.

The rolling-wave loop continues. Wave 6 (caches + corpora) will pick
up where this gate closes; wave 7 (connector + export governance) and
the future ciphertext-payload-wiring ADR remain on the roadmap.
