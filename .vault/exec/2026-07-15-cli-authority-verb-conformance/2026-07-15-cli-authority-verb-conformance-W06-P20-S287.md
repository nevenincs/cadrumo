---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S287'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Bisect the documentation lane with no workers and name the module whose worker exits, since it stalls identically at 24 and at 4 workers and emits no failure identities

## Scope

- `dev/docs/tests/test_docs_build.py`

## Description

- Run the documentation lane verbosely at four workers and LET IT RUN, which is
  the one thing three prior attempts did not do.
- Attribute the node-down to the test the dying worker was executing.

## Outcome

SATISFIED. The worker death is identified, attributable, and NOT fatal.

The line, captured verbatim with per-worker attribution:

```
[gw2] node down: Not properly terminated
[gw2] [ 96%] FAILED dev/docs/tests/test_docs_catalogue_drift.py::test_catalogue_msgids_match_current_source[es]

replacing crashed worker gw2
```

So the crash belongs to the catalogue-drift gate's Spanish parametrisation, and
xdist attributed the failure to exactly that case, replaced the worker, and the
run CONTINUED.

THE PRIOR DIAGNOSIS WAS WRONG IN ITS CONCLUSION, THOUGH RIGHT IN ITS
OBSERVATION. Three earlier attempts saw a node-down, saw no further progress,
concluded the lane was stalled, and killed it - twice at 74 per cent. The lane
was not stalled. Run verbosely and left alone, it passed 74, passed the
node-down at 96, and reached 98 per cent, where it sits on the full-scope
nitpicky Sphinx build, which the tree itself documents as taking roughly 840
seconds because it shells a complete single-worker documentation build and then
reads every rendered page.

Two things made the earlier attempts unreadable, and both are capture problems
rather than lane problems. Quiet mode pads its progress line and flushes only
complete lines, so a healthy run legitimately emits nothing for long stretches.
And killing the run destroyed the evidence of whether it would recover - which
it does, because xdist's response to a dead worker is to replace it.

Corpus: 206 items across 4 workers, 202 outcome lines observed, 6 failures at
the point of writing, one crashed-and-replaced worker.

Gates at HEAD `6b7ad7e0e8eab2deba1437e2ff2350e562b10dc5`:

- `uv run --no-sync pytest -v -rA -m docs -p no:cacheprovider -p no:randomly
  --tb=line -n 4 dev/docs/tests dev/docs/apidocs/tests
  src/cadrumo/tests/test_docstring_core_struct_links.py`, full output captured
  to a log with no truncation in the pipeline. `created: 4/4 workers`,
  `4 workers [206 items]`.
- Node-down attributed to
  `test_docs_catalogue_drift.py::test_catalogue_msgids_match_current_source[es]`.

## Notes

The row asked for three things and the third was the one that mattered: run it
verbosely, capture per worker, and LET IT COMPLETE rather than killing it. The
first two make the death attributable; only the third establishes that it is
survivable. A killed run cannot distinguish a crash the framework recovers from
and a crash that ends the lane, and those are very different defects.

Whether the lane finishes green is NOT settled here and belongs to the
full-lane row. This row establishes which worker died, on which test, and that
the run proceeds afterwards.
