---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:dca2ec53fb450a91d36107580c6b05252d042a23704cb0dad76039844457c2af'
step_id: 'S38'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Implement invocation-scoped operator-surface reconciliation reuse at the canonical CLI action-resolution boundary without process-global caching or weaker typed actions and notices.

## Scope

- `src/cadrumo/entrypoints/cli/_common.py`
- `src/cadrumo/entrypoints/cli/tests`

## Description

- Reuse one frozen `OperatorSurfaceReconciliation` through the shared context metadata of each upstream Click or vendored Typer invocation.
- Retain fresh live construction for callers outside an active command context and fail closed on an invalid context value.
- Keep action resolution on the existing catalogue, live input-schema, provenance, required-input, sanitization, and rendering paths.
- Prove both runtime stacks through real root-to-leaf runner dispatch, including reuse within one invocation and equivalent reconstruction across separate invocations.

## Outcome

The canonical action-resolution boundary now constructs the descriptor-backed live operator inventory at most once per command invocation. Nested command contexts and every action-bearing notice in an overview batch share the same immutable object; the next root invocation receives a distinct reconstruction. No process-global reconciliation cache or alternate resolver was introduced.

The focused action-resolution and invocation-lifecycle suites passed with fourteen tests. The two owning overview-status tests passed. Ruff check and format verification passed for all owned Python files. A bounded public `overview status` smoke run returned the current typed absent-session refusal in 8.736 wall seconds; it establishes that the public route is bounded, not healthy-profile performance. The construction-count and healthy performance proof remains owned by the next Step.

## Notes

An existing peer change adding the shared `notice_lines` renderer occupied a separate hunk in `_common.py`. It was preserved byte-for-byte while this Step used non-overlapping integration points.

Formal review found no production correctness issue. Its initial MEDIUM lifecycle-proof and LOW marker findings were resolved by moving the proof to an integration-marked module and driving both real Click runners instead of manually entering one context type.
