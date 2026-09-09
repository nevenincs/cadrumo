---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d797461005e4632de994b35cba6d2806f567d215798fdba5d6b7b012a1c5c7a5'
step_id: 'S308'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the UTC-validator detector's embedded executable source probes while retaining its no-allowlist live-tree ownership assertion and canonical UTC behavior.

## Scope

- `UTC validator enrollment detector fixtures`
- `focused gate`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/tests/test_utc_validator_enrollment_inventory.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/records.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S308.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_utc_validator_enrollment_inventory.py src/cadrumo/domain/contribuyente/inventory/tests/test_closing_authority.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The live gate exposed a duplicate awareness-only validator on a field already declared as `UtcInstant`; deleting the weaker validator left canonical UTC validation and 26 focused behavior tests green. The exact production detector remains red on the wider campaign findings.
