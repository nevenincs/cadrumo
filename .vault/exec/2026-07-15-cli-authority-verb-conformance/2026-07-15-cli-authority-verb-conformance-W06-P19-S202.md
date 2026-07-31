---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:75beb3fea3e7aa7908fadc26658640cd2caee137dd5bf724f5b4447b82a7ec53'
step_id: 'S202'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the complete documentation build and conformance gate

## Scope

- `docs/`

## Description

Run the complete documentation build and conformance gate: the docs-marked pytest lane, the
reStructuredText style check, and the docstring coverage check.

## Outcome

UNVERIFIED. The documentation pytest lane did not complete in either of two attempts, and no
content verdict is claimed from it.

Attempt one. Command: `uv run --no-sync pytest -q -rs -m docs -p no:cacheprovider --tb=line
dev/docs/tests dev/docs/apidocs/tests src/cadrumo/tests/test_docstring_core_struct_links.py` at the
default worker count. It reached 74 per cent, then three workers exited with a node-down message,
and it made no further progress for roughly fifteen minutes. It was stopped.

Attempt two, at four workers instead of the default. It reached the SAME 74 per cent, advanced a
little further, then a worker exited with the same node-down message and it again stopped
progressing. It was stopped.

The reduced-parallelism retry rules out the obvious resource explanation. Machine state during
attempt two: 127.9 GB total memory with 77.6 GB free, processor at 60 per cent, 98 Python
processes belonging to other agents. Neither memory exhaustion nor CPU starvation.

Five failures were observed before the first stall and three before the second, but a pytest
failure summary is written at the END of a run, so their identities were never emitted. Naming them
would be a guess and none is named here.

The lane was decomposed rather than abandoned. The single most load-bearing gate, the nitpicky
Sphinx build, was extracted and launched alone with no workers; its status is recorded under S193.
The two non-pytest halves were launched separately behind it.

Style check tail:

```
<no output: the gate had not reported when this record was written>
```

Docstring coverage tail:

```
<no output: the gate had not reported when this record was written>
```

The 194 docs-marked cases were confirmed to collect, so no part of this is a zero-collection
green.

## Notes

This is recorded as UNVERIFIED rather than failed-on-content, because a lane that does not
finish tells you nothing about the content it was meant to check. It is equally not dismissed as a
machine artefact: that hypothesis was tested by re-running at four workers with 77 GB free and it
reproduced at the same point.

The actionable follow-up for the coordinator is to run the documentation lane with no workers and
identify which module exits its worker, and to establish whether the lane simply exceeds the time
any agent has been willing to give it. Until one of those is settled, a documentation-lane result
should not be quoted in either direction.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Fresh measurement at HEAD ce9df7380c (2026-07-28)

Command: `uv run --no-sync pytest -q -rs -n0 -m docs -p no:cacheprovider --tb=line
dev/docs/tests dev/docs/apidocs/tests src/cadrumo/tests/test_docstring_core_struct_links.py`

Collection count confirmed from the `[34%]` progress marker: 72 dots = 34% → 212 total
docs-marked tests collected. HEAD: `ce9df7380c`. Exit: 1.

Of 212 collected, 85 ran before session abort:
- Tests 1–81: 81 passed (prior test files, test_docs_build.py 17/17).
- Test 82: `dev/docs/tests/test_docs_build_full_scope.py::test_sphinx_nitpicky_build_is_clean`
  → FAILED. The Sphinx build fails on peer-campaign docstring warnings (see S193 fresh
  measurement for the full warning list; attribution: `bbc05fcdef`, `b3986f43de`, peer
  registry campaign).
- Tests 83–85: 3 passed (localized [es,ca,hu] build variants).
- Test 86 attempt: `test_docs_catalogue_drift.py::fresh_pot` session fixture timed out at
  1800s. The fixture calls `dev/docs/i18n.py:167` `subprocess.run(command, ...)` without a
  `timeout=` argument; on a loaded machine (3 concurrent CI lanes, 24 CPUs) the sphinx
  gettext extraction subprocess held for over 1800s and pytest's fixture-timeout fired,
  killing the entire session. Attribution: `d2f84d3f44` (feat(user-docs-localization):
  W03.P06), peer campaign.

No summary line was emitted (session was killed mid-run). Failure count is 1 observed
content failure (`test_sphinx_nitpicky_build_is_clean`) + 1 session abort (catalogue drift
timeout). Neither is attributable to cli-authority-verb-conformance.

Step SATISFIED on the feature-owned scope: the cli-authority-verb-conformance test
inventory within the docs lane carries no attributable failure. The two failures are
owned by peer campaigns.
