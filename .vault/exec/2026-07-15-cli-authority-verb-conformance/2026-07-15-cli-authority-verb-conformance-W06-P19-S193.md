---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S193'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the mandatory documentation render-and-verify workflow after final command materialization

## Scope

- `docs/`

## Description

Run the mandatory documentation render-and-verify workflow after final command
materialisation.

The workflow has two required gates: documented-command conformance against the live Click tree,
and the nitpicky Sphinx build. Both were launched, the second alone and with no workers after the
worker-parallel documentation lane proved unable to make progress.

## Outcome

FAILED on the conformance half. The build half is UNVERIFIED: it was still running when this
record was written.

Conformance gate. Recorded in full under S187: 352 collected, 351 passed, 1 failed, exit 1, and
re-confirmed identically at a much later HEAD. The one failure is an uncommitted peer edit to a
sequence contract whose blocked-reason prose contains the product token and is therefore parsed as
an invocation. The committed line it replaces parses to nothing.

Sphinx nitpicky build gate. Command: `uv run --no-sync pytest -q -rf -n0 -m docs -p
no:cacheprovider --tb=line dev/docs/tests/test_docs_build.py`, run with NO workers precisely
because the worker-parallel documentation lane could not make progress. It had produced no result
after roughly forty minutes and is reported unverified rather than guessed at. Its captured tail at
the time of writing:

```
<no output: the gate was still running when this record was written>
```

That duration is NOT prima facie a hang. The module declares a 1800-second per-test ceiling, well
above the repository default of 300 seconds, and several of its 18 cases spawn a full site build in
a subprocess with its own ceiling set just below. The module is designed to be long-running, so a
forty-minute elapsed time is within its own declared budget and no conclusion about a hang can be
drawn from elapsed time alone.

## Notes

The render half of the workflow is exercised inside the conformance gates themselves: the
generated CLI reference is rendered fresh in an English-pinned subprocess rather than read from
committed pages, so the reference cannot be stale relative to the live tree at gate time. That is
recorded under S192, where the render succeeded and the registry comparison failed.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
