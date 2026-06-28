---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S86
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W03.P09 — filed-list payload class and emit migration

## Outcome

Authored `_app_live_payloads.py` with `FiledListResult` OutputSchema subclass registered as `app.live.filed.list` and the shared `FiledListingRowPayload` sub-model. Migrated the `filed_list_cmd` bare `_emit(ctx, payload_dict, lines)` site to `_emit_envelope`. The nested row list is constructed by explicitly mapping each `FiledDataListingRow` to `FiledListingRowPayload` with `presented_at` serialised via `.isoformat()` to satisfy the `str` field type.

## Files changed

- `src/aeat/entrypoints/cli/_app_live_payloads.py` — new file with `FiledListResult` and `FiledListingRowPayload`
- `src/aeat/entrypoints/cli/_app_live.py` — `filed_list_cmd` bare emit site migrated

## Gate

57 tests passed (21 live-subgroup + 36 conformance).
