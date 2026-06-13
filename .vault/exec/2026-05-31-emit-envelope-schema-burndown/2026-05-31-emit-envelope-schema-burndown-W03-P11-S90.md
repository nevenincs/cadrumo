---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S90
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W03.P11 — filed-capture-sources payload class and emit migration

## Outcome

Authored `FiledCaptureSourcesResult` OutputSchema subclass in `_app_live_payloads.py` registered as `app.live.filed.capture.sources`. Field set mirrors `SourceFiledDataCaptureReport` exactly (`target_modelo`, `target_year`, `target_period` replace the `modelo`/`year` fields). Migrated `filed_capture_sources_cmd` bare `_emit(ctx, report, lines)` site to `_emit_envelope`.

## Files changed

- `src/aeat/entrypoints/cli/_app_live_payloads.py` — `FiledCaptureSourcesResult` added
- `src/aeat/entrypoints/cli/_app_live.py` — `filed_capture_sources_cmd` bare emit site migrated

## Gate

57 tests passed (21 live-subgroup + 36 conformance).
