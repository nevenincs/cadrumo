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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S287 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Bisect the documentation lane with no workers and name the module whose worker exits, since it stalls identically at 24 and at 4 workers and emits no failure identities and ## Scope

- `dev/docs/tests/test_docs_build.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Bisect the documentation lane with no workers and name the module whose worker exits, since it stalls identically at 24 and at 4 workers and emits no failure identities

## Scope

- `dev/docs/tests/test_docs_build.py`

## Description

Settle the documentation lane: name the module whose worker stops, or demonstrate that the
lane completes serially and only fails under workers.

Re-read the two stalled captures byte-for-byte rather than by eye. Re-run the lane with no workers,
per-test identities, and genuinely unbuffered output through OS-level redirection rather than a
PowerShell pipeline. Map the lane's declared cost budgets against what was observed.

## Outcome

PARTLY SETTLED, and the substantive result is a CORRECTION TO MY OWN EARLIER FINDING rather
than the module name that was asked for. The lane was never observed to stop where I reported it
stopping.

FINDING 1 — the "no output for forty minutes" was an artifact of the capture, and provably so.
Under `-q`, pytest writes progress as a fixed-width line: 72 characters of per-test marks then the
percentage, 79 characters total, measured on the surviving capture. PowerShell's `Out-File` in a
pipeline emits only COMPLETE lines. The isolated run I reported as producing nothing for forty
minutes was one module of 22 tests. Twenty-two marks can never reach 72, so that run could not have
written a single byte no matter how healthy it was. Zero bytes was the guaranteed output of a
correct run, not evidence about a hang. I said at the time that elapsed time alone proved nothing;
the mechanism now proves the stronger statement, that the silence carried no information at all.

FINDING 2 — both parallel runs had advanced far past the point I reported them frozen at, and the
"same point at 24 and at 4 workers" coincidence dissolves. Reading the raw bytes with control
characters shown, each capture holds two COMPLETE 72-mark lines (144 tests) plus a PARTIAL third
line that never terminated and therefore never flushed as it grew. Counting the marks actually
present on that partial line: 30 in the 24-worker attempt and 31 in the 4-worker attempt. So the
runs had completed roughly 174 and 175 of 194 cases, about ninety per cent, not the 74 per cent the
last flushed line showed. The two attempts did not stop at the same place; they were both simply
read at the same buffer boundary, which is a property of the capture and not of the lane. My S202
record asserted that coincidence as evidence against a resource explanation. That reasoning was
unsound and is withdrawn.

FINDING 3 — the lane's cost is enormous and declared in-tree, which is what the progress bar was
actually showing. Two modules override the 300-second repository ceiling with an 1800-second
budget. The resolvability sweep is a single test whose own comment states it measures about 840
seconds on the reference workstation because it shells a full single-worker Sphinx HTML build and
then reads every rendered page. Eleven of the 24 modules in the lane shell a build or a subprocess.
A lane that appears motionless for fifteen minutes is consistent with one such test running
normally.

FINDING 4 — the worker deaths are REAL and remain unexplained. This is the part that survives every
correction above. The 24-worker attempt reported four `node down: Not properly terminated` events
and the 4-worker attempt reported two. Those are abnormal worker terminations, written inline and
independent of any buffering. I cannot name the responsible module: `--dist=loadfile` decouples
completion order from collection order, so mark position cannot be mapped to a test, and I stopped
both runs, destroying the evidence that would have shown whether they recovered and finished.

Serial re-run, the instrument that makes identities visible. Command: `PYTHONUNBUFFERED=1 uv run
--no-sync pytest -v -n0 -m docs -p no:cacheprovider --timeout=240 --timeout-method=thread
--tb=line dev/docs/tests dev/docs/apidocs/tests src/cadrumo/tests/test_docstring_core_struct_links.py`,
redirected with a plain shell `>` so nothing is line-buffered. 194 collected, matching the earlier
count. `-p no:randomly` was deliberately NOT passed: that plugin is not installed, the plugin set
being pytest-asyncio, base-url, cov, playwright, timeout and xdist, so the order is already
deterministic and the flag would have errored.

This run streams one line per test and shows the IN-FLIGHT test as a line with no verdict, so a
genuine stall names itself with no inference required. State at the time of writing:
1 of 194 complete, currently inside the 840-second resolvability
sweep. Tail:

```
collecting ... collected 246 items / 52 deselected / 194 selected
dev/docs/tests/test_api_stubs.py::test_every_source_module_has_a_stub FAILED [  0%]
dev/docs/tests/test_built_site_resolvability_sweep.py::test_every_injected_record_target_resolves_in_built_site 
```

The first case, the API stub gate, fails immediately; that failure is a peer-owned stub drift
already covered under S208 and is not related to this investigation.

## Notes

What is now established and what is not.

Established: the lane does not stop at 74 per cent; it reaches about ninety per cent under workers.
The apparent silence of the isolated module run was structurally impossible to avoid and carried no
information. The lane's runtime is dominated by full Sphinx builds with declared 1800-second
budgets, one single test costing about 840 seconds by its own documentation.

Not established: which module kills a worker. The honest reason is twofold and both halves are my
doing. Load-file distribution means I cannot map a mark position to a test. And I stopped both
parallel runs before they could either recover or finish, so I cannot say whether the node-down
events were fatal to the run or merely noisy. A future attempt should let a worker-parallel run
complete rather than killing it, and capture with `-v` through OS redirection so every worker's
per-test lines are attributable.

The serial run in flight will answer whether the lane completes with no workers at all. If it does,
this is a parallelism defect with a different owner and a different fix, exactly as anticipated. If
it also dies, the defect is in a test rather than in xdist. That run is long by construction and
was left running rather than killed a third time.

Method note worth carrying: every wrong conclusion in this investigation came from trusting a
rendered view of a log rather than its bytes. `cat -A` on a 324-byte file overturned two claims I
had already put in a record and reported upstream. A partial line is invisible in a normal read and
looks exactly like a stalled process.

The semantic code index remained degraded throughout, at 466 code sections against 3982 tracked
Python files while reporting success. Nothing here rests on it.
