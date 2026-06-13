---
step_id: S76
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P02.S76 — attach_run_sink scrubbing end-to-end test

## Outcome

Extended `src/aeat/core/observability/test_sink_redaction.py` with
`test_run_scoped_records_scrubbed_before_reaching_jsonl_via_attach_run_sink`.

The test exercises the full path: `attach_run_sink(sink)` → emit a `RunEvent`
carrying `_NIF_CANARY` → read the JSONL file → assert plaintext NIF absent.
Uses real `JsonlRunSink`, real `attach_run_sink`, real temp path. No mocks.
The run_id on the event matches the sink's run_id so the event passes the
cross-run guard and reaches the serialiser.

## Files touched

- `src/aeat/core/observability/test_sink_redaction.py`

## Verification

`uv run --no-sync pytest src/aeat/core/observability/test_sink_redaction.py -q` — 6 passed.
