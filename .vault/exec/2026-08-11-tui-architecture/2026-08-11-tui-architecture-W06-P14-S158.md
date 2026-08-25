---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:bbd349100862648a556cb2f1355586051dfa7ea20c8a03b2f39a12214b11f4f8'
step_id: 'S158'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Delete duplicate JSON and SHA-256 mechanics from operation-adjacent paths

## Scope

- `src/cadrumo/application/flows/_definition.py`
- `src/cadrumo/application/filing/_review.py`
- Focused flow and filing parity tests

## Description

- Import `content_hash_hex` directly from the canonical `cadrumo.core.hashing` defining module.
- Delete local JSON serialization, SHA-256 construction, and `_sha256_payload` authority.
- Preserve domain payload normalization, ordering, and legacy byte identity.
- Add focused parity tests, including non-ASCII flow type-token coverage.
- Run semantic RAG and exact zero-remnant searches.

## Outcome

Both production paths use the single canonical hashing authority. Exact searches find no target-local `json.dumps`, `hashlib.sha256`, SHA alias, shim, fallback, re-export, or duplicate helper.

Independent review approved the row. Eight focused parity and stability nodes passed; targeted Ruff and basedpyright passed. The former streamed invoice and transaction JSON digests are byte-identical.

## Notes

A broader three-module run passed 26 tests and failed one unrelated pre-existing runtime-storage refusal assertion whose expected prose no longer matches the concurrent storage error catalogue.

