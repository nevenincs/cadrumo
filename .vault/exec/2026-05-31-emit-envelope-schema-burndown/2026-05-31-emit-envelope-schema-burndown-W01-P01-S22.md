---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S22
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W01.P01 — ledger mutation verbs

## Outcome

Authored `_ledger_payloads.py` with all 11 mutation-verb `OutputSchema` subclasses (`LedgerAddResult`, `LedgerUpdateResult`, `LedgerClassifyResult`, `LedgerAllocateResult`, `LedgerAttachResult`, `LedgerArchiveResult`, `LedgerStashResult`, `LedgerRemoveResult`, `LedgerResetResult`, `LedgerSplitResult`, `LedgerMergeResult`) each decorated with `@register_schema`. Migrated all 11 bare `_emit(ctx, payload_dict, lines)` sites in `_ledger.py` to `_emit_envelope` calls.

Shared `_emit_update_result` helper extended with `command: str` and `result_cls: type` keyword parameters so each mutation verb passes its specific registered schema class. All nested `model_dump` calls use `mode="json"` (not `mode="python"`) to satisfy `OutputSchema`'s `strict=True` constraint — strict mode rejects Python tuples where `list[str]` is declared.

## Files changed

- `src/aeat/entrypoints/cli/_ledger_payloads.py` — new file with 11 mutation-verb schemas
- `src/aeat/entrypoints/cli/_ledger.py` — 11 bare emit sites migrated

## Gate

109 ledger CLI tests + conformance gate passed.
