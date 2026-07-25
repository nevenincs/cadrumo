---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
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
