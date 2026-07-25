---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S92'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delegate MCP telemetry content digests to core sha256_hex

## Scope

- `src/cadrumo/entrypoints/mcp/_telemetry.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `604c8dce53` routed sixteen production one-shot SHA-256 bodies through `core.hashing.sha256_hex`, including this module.

- Route the MCP telemetry content digest through `core.hashing.sha256_hex` instead of an inline `hashlib.sha256(...).hexdigest()` body.
- Preserve the UTF-8 encoding at the call site so the digest bytes stay identical by construction.

## Outcome

`src/cadrumo/entrypoints/mcp/_telemetry.py` imports `sha256_hex` from `...core.hashing` at line 39 and calls it at line 91 to build the retained telemetry record's content digest.

Verified against HEAD: the import and call site match the commit's stated scope, and the sibling Step S93 proof (`test_telemetry_retention.py`) exercises the delegated digest against a known SHA-256 vector and a real retained-record roundtrip.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/entrypoints/mcp/tests/test_telemetry_retention.py` reports 10 passed.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
