---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S15'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Write comparison tests covering JSON match and mismatch diagnostics, text match, exit-code failure, and @expect pass and fail

## Scope

- `dev/docs/sequences/tests/test_compare.py`

## Description

- Produce every golden under test from a REAL sandboxed CLI execution (`config profile list` sequences, JSON and text variants) projected through the real store — no hand-shaped fixtures.
- Prove the clean path end to end: golden written from run A, a fresh sandboxed run B compares with zero problems through the full `check_transcript` tier, covering masking and text normalisation across two real runs.
- Prove the store roundtrip with strict model equality, the canonical review-diffable file form, the missing-golden refusal naming the refresh invocation, and the strict-schema refusal of a hand-edited golden carrying a smuggled mask-extension key.
- Red every divergence class by mutating the committed artifact: envelope status drift (named frame and differing path), a deleted envelope field (the anti-tautology proof), exit-code drift, frame-count drift, capture-value drift, and text drift (unified diff with the exact removed line).
- Cover `@expect` pass, semantic failure quoting the live value, and missing-path diagnostics against the live run, plus a signature gate pinning that no comparison function accepts a mask or fields parameter.

## Outcome

17 real-behaviour tests green (68 across the whole engine suite), each mismatch reported with the page, sequence id, frame index, argv, and the refresh remedy. The deleted-field mutation proves a corrupted stored payload cannot pass, so the suite's clean passes are non-tautological.

## Notes

Strict python-mode validation refuses JSON-document lists for tuple fields, so golden mutation in tests re-validates through JSON mode exactly as the store's reader does.
