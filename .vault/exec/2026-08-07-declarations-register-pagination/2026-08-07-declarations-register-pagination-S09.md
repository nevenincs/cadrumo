---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:6e37cc27044334ff55bd90ebbbc15154d3cd49df59d02c9787a5ed3187217942'
step_id: 'S09'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
## Description

The sibling row proved cross-pair continuation for the listing function and left
the capture function's own loop unwalked, because covering it pulls a real
encrypted bucket into a browser test. That cost is what this row pays: a second
continuation test standing up a genuine active-profile bucket runtime beside the
real headless page the listing test already proved reachable offline.

Nothing in production changed. The register-injection seam this test drives
through was already in place; only its capture-side loop was unproven.

## Outcome

- New test module `test_filed_bulk_capture_continues_past_a_failed_pair` under
  the live application tests. One test, one property.
- Real throughout: a real `AeatSession`, a real headless Chromium page, a real
  `DeclaracionesRegisterSession`, a real bucket runtime from the shared isolated
  runtime-profile helper, the real form drive, the real parse and the real
  capture loop. Only the network is intercepted, and only with the two synthetic
  fixtures the sibling row introduced. No stub, no patched production path.
- The live-read gate is never satisfied and the live-tests environment flag is
  never set. Bypassing session resolution through the injected register is what
  keeps this from arming real AEAT access, which is the whole reason the seam
  exists.
- Continuation is asserted on the SHAPE of the outcomes rather than on a tally,
  as the row requires: a walk-level refusal carries no expediente because no row
  was ever parsed, while anything the reached pair produces carries one. A
  capture that halted at the refused pair could only ever produce the first kind.

## Verification

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_bulk_capture_continues_past_a_failed_pair.py -q -p no:randomly -n 0
    1 passed in 32.18s

Whole owning package, to confirm nothing else moved:

    uv run --no-sync pytest src/cadrumo/application/live/tests/ -q -p no:randomly
    326 passed in 61.55s (0:01:01)

`ruff check` and `ruff format --check` clean on the new module; the full type
run reports zero diagnostics in it.

Mutation proof, through a pytest plugin held OUTSIDE the repository so no tracked
file changed and a crashed run leaves no residue. The plugin rebinds the shared
per-pair absorber to propagate instead of absorb:

    PYTHONPATH=Y:/ uv run --no-sync pytest <module> -q -p no:randomly -n 0 -p mutate_absorber
    1 failed

and it reds for the right reason rather than incidentally — the truncation
refusal escapes the loop at the absorber's own call site:

    src/cadrumo/application/live/_filed_data_capture.py:626: in capture_filed_data_bulk
    SedeParseError: declaraciones register modelo 100 ejercicio 2025 rendered 3 row(s)
    but its pager declares 8 in total; refusing an under-reported filing history

Restored by dropping the plugin; green again.

## Notes

DEVIATION FROM THIS ROW'S WORDING, recorded here so a plan reader sees it without
opening test internals. The row asks that the complete pair "still captures its
observations". It does not, and the assertion is written on the shape of the
outcomes instead. The wording assumed route interception could reach the
justificante PDF leg; it structurally cannot, and that was measured rather than
assumed. The cotejo PDF is fetched through an API request context, which no
page-level or context-level route handler is consulted for — an intercepted
request against the sede host returned a real response from the real host with
the handler never invoked. Driving the capture far enough to persist an
observation offline would therefore need either a production change or genuine
AEAT contact, and this row forbids the second outright.

The property the row exists to prove, cross-pair continuation, is proven either
way. Observed shape: the 2025 pair refuses at the walk with no expediente; the
2024 pair is walked, parsed, and both its rows reach per-row processing, each
outcome carrying its expediente id. The assertion is phrased as "an observation
OR a per-row outcome" deliberately, so it keeps holding rather than inverting
into a false alarm if that leg ever does become reachable offline. The
measurement is also recorded in the test's own docstring, so nobody closes the
apparent gap by wiring a real fetch.

The measurement that established this cost one unauthenticated request to a
nonexistent path on a real AEAT host. That was disclosed at the time and should
not be repeated: a future check of whether interception reaches a given call site
belongs against a local synthetic target, never a real AEAT hostname, regardless
of authentication or write status.
