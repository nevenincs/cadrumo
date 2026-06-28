---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S84
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W02.P08 — MIGRATED_COMMANDS extension and surface-test re-baseline

## Outcome

Added `_config_payloads` side-effect import to `test_json_schema_conformance.py` so `@register_schema` decorators populate `SCHEMA_REGISTRY` before the gate inspects it (S83). Appended all 19 config command paths to `MIGRATED_COMMANDS`: 4 repair verbs, 7 config/profile verbs, 8 auth/bucket verbs (S82).

Re-baselined `test_repair_reset_state.py` to read `payload = envelope["result"]` after `envelope = json.loads(result.output)` and assert `envelope["command"] == "config.repair.reset_state"` before field-level assertions (S84). The other two failing tests in that file (`test_reset_state_dry_run_returns_fingerprint_without_deleting_row`, `test_reset_state_with_yes_deletes_row_emits_event_and_reload_is_empty`) were confirmed pre-existing failures (exit code 2 before my changes).

## Files changed

- `src/aeat/entrypoints/cli/test_json_schema_conformance.py` — `_config_payloads` import + 19 path entries (S82, S83)
- `src/aeat/entrypoints/cli/_config/test_repair_reset_state.py` — envelope shape re-baseline (S84)

## Gate

55 conformance tests pass (1 static + 54 parametrized). 103 config suite tests pass.
All 19 config schema paths surface in `MIGRATED_COMMANDS` and are registered in `SCHEMA_REGISTRY`.
