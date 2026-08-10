---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:6f47d614d03db597b4655f0e340ff6ed73efd2e6c96dee3c2a26fea9ca274e86'
step_id: 'S16'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-08-10-m303-carry-reconciliation-s16-submitted-file-notice-route-reference]]"
  - "[[2026-08-10-m303-carry-reconciliation-s16-submitted-file-notice-route-audit]]"
---

# Surface a recorded submitted-file layout refusal to the operator through the Notice channel, completing the fail-hard-and-loud directive rather than enhancing it. The refusal itself now raises with modelo, resolved revision, ejercicio, period, expediente id, artefact digest and the parser's own reason. Its single production consumer catches it and writes metadata submitted_file_extraction_error, then degrades to the declaration-PDF path. Measured. Nothing in the codebase reads that metadata key. No Notice, no CLI field, no operator surface. So the capture is strictly louder than the silent positional fallback it replaced, which produced silence plus fabricated values plus a fabricated 1.0 extraction coverage that passed the coverage gate, and it is still not loud where the operator is. Notices are the only sanctioned diagnostic channel, so the advisory belongs there and MUST NOT be a bespoke advisory or next field inside a result payload. Gate. A capture whose submitted-file layout parse fails emits an advisory Notice naming the modelo and the failed record, proven by a test that makes the parse fail and asserts the Notice reaches the envelope, with a positive control proving a successful capture emits no such Notice

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede`
- `src/cadrumo/application/live`

## Description

- Preserve the Sede parser refusal verbatim in observation metadata before the declaration-PDF fallback runs.
- Project recorded submitted-file extraction refusals into the shared capture Notice lane.
- Carry that lane through single, bulk, source and all-history pull envelopes without changing result schemas.
- Split the proof by adapter, application and CLI ownership after the first review identified an inward test dependency.

## Outcome

The operator receives one warning with the modelo, filing coordinates,
expediente and parser reason whenever an otherwise-captured submitted fichero
cannot be read by its declared layout. A clean submitted-file read emits no such
notice. The adapter's metadata and declaration-PDF fallback stay unchanged in
meaning, and diagnostics remain exclusively on the envelope notice channel.

## Verification

`uv run --no-sync pytest -m integration src/cadrumo/adapters/outbound/aeat/sede/tests/test_submitted_file_layout_refusal.py src/cadrumo/application/live/tests/test_submitted_file_extraction_notice.py -q`

`16 passed in 19.62s`

`uv run --no-sync pytest -m unit src/cadrumo/application/live/tests/test_filed_bulk_capture.py src/cadrumo/application/live/tests/test_filed_history_composition.py src/cadrumo/application/live/tests/test_recapture_divergence_enrolment.py src/cadrumo/entrypoints/cli/tests/test_app_live_filed_notice_relay.py -q`

`24 passed in 15.09s`

`uv run --no-sync ruff check` over the S16 sources and tests returned `All checks passed!`.

`uv run --no-sync basedpyright` over the S16 tests and capture/report sources returned `0 errors, 0 warnings, 0 notes`.

## Notes

The first independent review found one high boundary issue: an outbound-adapter
test imported private application and CLI modules. The proof was relocated by
owner and the second independent review was clean. The broader type invocation
still reports pre-existing errors in legacy Sede and CLI modules outside this
Step's changed lines; no S16-line type error was reported.
