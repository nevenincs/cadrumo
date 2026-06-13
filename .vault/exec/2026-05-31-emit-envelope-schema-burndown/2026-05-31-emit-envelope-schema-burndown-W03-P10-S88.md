---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S88
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W03.P10 — filed-capture payload class and emit migration

## Outcome

Authored `FiledCaptureResult` OutputSchema subclass in `_app_live_payloads.py` registered as `app.live.filed.capture`. Field set mirrors `FiledDataCaptureReport` exactly; `tuple[str, ...]` fields declared as `list[str]` per W01 discipline. Migrated `filed_capture_cmd` bare `_emit(ctx, report, lines)` site to `_emit_envelope`, constructing `FiledCaptureResult` from the `FiledDataCaptureReport` fields with `list()` coercion on all tuple sequences.

## Files changed

- `src/aeat/entrypoints/cli/_app_live_payloads.py` — `FiledCaptureResult` added
- `src/aeat/entrypoints/cli/_app_live.py` — `filed_capture_cmd` bare emit site migrated

## Gate

57 tests passed (21 live-subgroup + 36 conformance).
