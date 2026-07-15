---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S14'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Implement text-frame exact comparison with declared narrow normalisation, per-frame exit-code assertion, and @expect semantic evaluation against live output

## Scope

- `dev/docs/sequences/_compare.py`

## Description

- Compare text frames by exact string equality after the declared narrow normalisation: the live output is normalised with THIS run's sandbox paths and centrally-masked id values, the golden already stores normalised text, and a divergence reports a unified diff (golden vs live) — no wildcards, no fuzzy matching, no contains-assertions.
- Assert the exit code on every frame (golden versus live), and report a frame whose output form flipped (JSON to text or text to JSON) as its own named problem.
- Implement `evaluate_expectations`: every `@expect` evaluates against the LIVE executed output — the `exit_code` pseudo-path against the frame's process exit code, every other json-path resolved into the live envelope — with named problems for a failed assertion (quoting the live value), a missing path (listing the envelope's top-level keys), and a json-path expectation on a non-JSON frame.
- Compose `check_transcript` (golden comparison plus live expectation evaluation, one problem list) and `assert_transcript_matches_golden`, which raises the accumulating mismatch error closing with the exact refresh invocation.

## Outcome

Golden equality proves the output is reproducible; the live `@expect` evaluation proves it means what the page claims — a sequence cannot verify by merely reproducing a failure. Both future gate surfaces call one `check_transcript`, keeping a single execution-and-comparison path.

## Notes

No incidents. Expectations are evaluated against the transcript rather than re-enforced by the runner (which only enforces exit codes at execution time), so the check tier reports semantic failures alongside golden drift in one worklist.
