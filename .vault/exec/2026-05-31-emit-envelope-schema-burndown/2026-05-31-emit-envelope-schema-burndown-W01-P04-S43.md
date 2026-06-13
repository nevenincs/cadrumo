---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S43
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W01.P04 — conformance gate extension and surface-test re-baseline

## Outcome

Extended `test_json_schema_conformance.py`: added `_ledger_payloads` to the side-effect import line (populates `SCHEMA_REGISTRY` before gate inspection), added all 20 ledger command paths to `MIGRATED_COMMANDS`.

Re-baselined 5 ledger surface-test files that previously asserted bare-payload JSON shape. The migration wraps all payloads in `SchemaEnvelope` with a `result` key, so every `json.loads(output)["field"]` assertion became `json.loads(output)["result"]["field"]`. Shared `_imported_transaction_id` and `_list_transactions` helpers updated to use `payload.get("result", payload).get("rows", [])`.

## Files changed

- `src/aeat/entrypoints/cli/test_json_schema_conformance.py` — `_ledger_payloads` side-effect import + 20 entries in `MIGRATED_COMMANDS`
- `src/aeat/entrypoints/cli/test_ledger_allocate_classification.py` — re-baselined
- `src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py` — re-baselined
- `src/aeat/entrypoints/cli/test_ledger_validation_paths.py` — re-baselined
- `src/aeat/entrypoints/cli/test_ledger_bulk_classify.py` — re-baselined

## Gate

109 ledger CLI tests + 33 conformance gate tests passed (142 total).
