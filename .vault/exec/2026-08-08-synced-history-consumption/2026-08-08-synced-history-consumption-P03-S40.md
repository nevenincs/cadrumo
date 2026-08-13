---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:91d303579dac0dee67e4b9e6c1a8857ba1bc190e0e0ef34a0942adfc61f09e9d'
step_id: 'S40'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Add bounded canonical sequence-runner progress and timeout diagnostics that identify page, sequence, and frame without changing golden or sequence semantics.

## Scope

- `dev/docs/sequences`
- `dev/docs/sequences/tests`

## Description

- Expose the existing child-process progress-journal supervision through the public `check --timeout SECONDS` command.
- Publish each progress receipt through the canonical atomic replacement helper so the supervisor never parses a torn write.
- Route bounded golden checks through one English-pinned child interpreter and return the latest runtime-derived page, sequence, frame ordinal, source locator, and resolved argv when its supervisor expires.
- Preserve the journal outside `SequenceTranscript`, golden payloads, expected-exit evaluation, and product runtime; no sequence or golden was refreshed.
- Preserve scoped page-coherence execution by forwarding its requested page through the same bounded child boundary.
- Prove the receipt against the enrolled `irpf-lifecycle-position` sequence rather than a synthetic delay or test seam.

## Outcome

The canonical runner records one non-golden, pre-invocation receipt immediately before each actual CLI frame. The public check command now accepts a positive bounded timeout and, on expiry, reports the last real page, sequence id, frame index and locator, and resolved command. A malformed or absent receipt remains a distinct honest message that no frame started before the deadline.

The real bounded diagnostic passed against the discovered `how-to/irpf-lifecycle` page with a 30-second supervisor bound. The assertion read the reported sequence and frame coordinate, resolved it against the page's current parsed `executed_frames`, and verified the source locator and argv without assuming which frame scheduling would reach. The bounded page-coherence public route also passed against a discovered temporary page.

Focused real child-interpreter evidence passed: 35 CLI tests passed, including strict deadline and receipt validation plus bounded coherence; the page-scoped bounded receipt proof passed serially in 31.82 seconds. Ruff check, Ruff format check, and scoped diff hygiene passed. Independent review passed after the synthetic private-helper test was deleted, atomic publication landed, and the timeout proof stopped pinning a scheduler-dependent frame.

## Notes

The progress receipt stays outside transcripts and goldens. No product runtime, frame schema, sequence contract, or golden changed. The public test derives page, sequence, frame, locator, and argv from production discovery; only the supervisor bound is the test's selected deadline.

