---
step_id: S64
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S64 — test: JSONL run sink records scrubbed before persistence

## Outcome

Extended `src/aeat/core/observability/test_context_propagation.py` with
`TestRunSinkScrubbing` (three real-behavior tests). Tests use real
`run_context`, real `record_event`, real JSONL file on disk:

- `test_nif_shaped_field_is_sha256_prefixed_in_jsonl`: emits a
  `GenericPayload` carrying a NIF-shaped value (`"12345678Z"`); reads
  `events.jsonl`; asserts the plain NIF is absent and `sha256:` prefix is
  present (DIAGNOSTIC-class redaction rule fired).
- `test_scrubbing_filter_present_on_sink_after_attach`: calls
  `attach_run_sink` directly; asserts `SecretScrubbingFilter` is installed
  on the handler before any records flow.
- `test_jsonl_lines_are_valid_json`: asserts every written JSONL line
  deserialises cleanly after scrubbing.

## Files touched

- `src/aeat/core/observability/test_context_propagation.py`

## Verification

`uv run --no-sync pytest src/aeat/core/observability/test_context_propagation.py -x -q` — 11 passed.
`vault plan step check S64` applied.
