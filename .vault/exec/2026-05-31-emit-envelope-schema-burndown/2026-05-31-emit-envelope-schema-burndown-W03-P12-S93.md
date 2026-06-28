---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S93
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W03.P12 — MIGRATED_COMMANDS extension and surface-test re-baseline

## Outcome

Appended `app.live.filed.list`, `app.live.filed.capture`, and `app.live.filed.capture.sources` to `MIGRATED_COMMANDS` in `test_json_schema_conformance.py`. Added `_app_live_payloads` side-effect import so `@register_schema` decorators populate `SCHEMA_REGISTRY` before the gate inspects it.

No re-baseline of `test_live_read_subgroups.py` was required: the existing test file covers `expedientes`, `verify`, `borrador`, and `iva_wallet` subgroups and does not assert bare-payload shape for the three `filed_*` commands migrated in W03.

## Files changed

- `src/aeat/entrypoints/cli/test_json_schema_conformance.py` — 3 paths added to `MIGRATED_COMMANDS`, `_app_live_payloads` side-effect import added

## Gate

57 tests passed (21 live-subgroup + 36 conformance). W03 close gate: all 57 pass sequentially.

## W03 summary

- 3 verbs migrated: `filed list`, `filed capture`, `filed capture-sources`
- 3 `OutputSchema` subclasses authored: `FiledListResult`, `FiledCaptureResult`, `FiledCaptureSourcesResult`
- 3 `MIGRATED_COMMANDS` entries added
- No discriminated unions needed: each command has a single payload shape
- Commits: `efe634d7d` (P09-P11 payloads + migrations), `8329e5543` (P12 conformance)
