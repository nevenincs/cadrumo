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

## Correction at HEAD `c7f0be2c6824161ec7831341aeb6baea9bad8186`: survivable was wrong, and the cause is upstream

SUPERSEDES the survivability claim above. The attribution stands; the
conclusion drawn from it does not, and the real cause is better than either.

WHAT I MISSED BY REPORTING TOO EARLY. I recorded the run as recovering because
I watched one worker die and be replaced. Left running, a SECOND worker died on
the SAME test: `gw2` at 96 per cent, then `gw1` at 99 per cent, both on
`test_catalogue_msgids_match_current_source[es]`. After the second death the
lane emitted nothing for 66 minutes. So the deaths are reproducible and
test-specific, and the lane does eventually wedge - which is what the earlier
attempts saw and reported, and what I contradicted on one death's evidence.

THE CAUSE IS NOT PARALLELISM. Run the module SERIALLY with no workers at all
and it still hangs, dying on pytest's own timeout inside
`subprocess.communicate` -> `WaitForSingleObject`. A defect that reproduces at
`-n0` cannot be worker contention.

THE CAUSE IS AN UNBOUNDED SHELLED BUILD. The module's POT fixture calls
`extract_pot`, which runs `python -m sphinx -b gettext` over the user-scope page
set via `subprocess.run(...)` with NO timeout argument. On this host that build
does not return. Everything else follows: serially pytest's timeout eventually
fires, and under xdist the unresponsive worker is reaped and reported as
`node down: Not properly terminated`. The node-down is a SYMPTOM of the hang,
not an independent defect.

Two hypotheses I formed and killed rather than shipping. The `-j` parallelism in
that command looked like a nested-parallelism culprit, but the build helper's own
docstring records that Sphinx parallel workers need `os.fork` and every `-j`
value degrades to serial on win32, so the knob changes nothing here. And a piped
stdout deadlock looked plausible, but the call passes no `capture_output` and no
pipes at all, so the streams are inherited and there is no buffer to fill.

WHAT IS ESTABLISHED, and what is not. Established: the hang reproduces serially,
it is in the shelled gettext build, and the call sets no timeout. NOT
established: why that Sphinx build does not return on this host. Naming a reason
would be a guess and none is offered.

The actionable defect independent of the underlying hang is the missing bound. A
gate that shells a build with no timeout converts any upstream hang into an
indefinite lane wedge with no diagnostic, which is precisely how this cost three
prior attempts and two premature verdicts, mine included.

Command: `uv run --no-sync pytest dev/docs/tests/test_docs_catalogue_drift.py
-n0 -m "" -p no:cacheprovider`, terminated by the harness timeout with a
`+++ Timeout +++` banner and a stack in `subprocess.communicate`.
