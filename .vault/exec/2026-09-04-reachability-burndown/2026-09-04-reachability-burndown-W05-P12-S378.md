---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:06eb4e292f749c5872bcd22e36499acbbf6a194f4832404cfe203d6896101fec'
step_id: 'S378'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---
# Resolve the remaining exact unreachable symbols in entrypoint and LLM ownership while preserving live command behavior.

## Scope

- `src/cadrumo/entrypoints`
- `src/cadrumo/llm`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact --full` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_cli.py src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_resolution_cli.py src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_duplicate_cli.py` -> `fail`

## Notes

- The focused entrypoint run passed 29 tests; `test_the_class_and_its_correction_can_be_stated_by_the_operator` remains red because the live invoice validator refuses its fixture before command success. The failure is outside the deduplicated parameter-forwarding path.
