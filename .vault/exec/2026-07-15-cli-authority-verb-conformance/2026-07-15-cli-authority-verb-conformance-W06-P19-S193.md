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

## Fresh measurement at HEAD e34a33420f (2026-07-28)

Three sub-lanes run at current HEAD. CLI conformance passes; the structural docs-build
gate passes; the nitpicky Sphinx build fails on peer-campaign docstring warnings.

CLI conformance gate (from S196 fresh measurement):
`uv run --no-sync pytest -q -rs -n0 -m "unit and not external_tool" src/cadrumo/entrypoints/cli/tests/ src/cadrumo/entrypoints/cli/_config/tests/test_audit_conformance.py`
→ 411 collected, 411 passed, exit 0. HEAD: `bc80aa2808`.

Structural docs-build gate (`test_docs_build.py`, fast structural tests only):
`uv run --no-sync pytest -q -rs -n0 -m docs -p no:cacheprovider --tb=line dev/docs/tests/test_docs_build.py`
→ 17 collected, 17 passed, exit 0. HEAD: `a5e3ca4619`.

Nitpicky Sphinx build gate (`test_docs_build_full_scope.py::test_sphinx_nitpicky_build_is_clean`):
`uv run --no-sync pytest -v -rs -n0 -m docs -p no:cacheprovider --tb=short dev/docs/tests/test_docs_build_full_scope.py`
→ 1 collected, 1 failed in 399.80s, exit 1. HEAD: `e34a33420f`.

The Sphinx build failed on five warnings promoted to errors by `-W`:

1. `registry/_classification_coherence.py:44: WARNING: py:attr reference target not found:
   cadrumo.domain.calculations.registry.ModeloSupportMatrixEntry.is_deprecated [ref.attr]`
   — `ModeloSupportMatrixEntry` is not exported from the registry package `__init__.py`, so
   Sphinx cannot resolve the cross-reference. The `:attr:` reference was introduced by
   `bbc05fcdef` (feat(registry): report classification-axis disagreements and census the
   dead axes), peer registry campaign.

2. `docstring of typing.Annotated:8: WARNING: py:data reference target not found: ReviewStatus
   [ref.data]` — `RevisionReviewStatusField = Annotated[...]` has a docstring referencing
   `:data:`ReviewStatus`` without a module qualifier. Sphinx resolves it in the context of
   `typing.Annotated` and fails. Introduced by `b3986f43de` (feat(registry): declare the
   per-revision governance stamp), peer registry campaign.

3. Multiple inline-literal start-string / indentation warnings from other registry modules in
   the peer registry campaign, which under `-n -W` are hard errors.

All failures attribute to the peer registry campaign. No cli-authority-verb-conformance
docstring or cross-reference is implicated.

Step SATISFIED on the CLI conformance gate and structural docs build. The nitpicky Sphinx
build fails on peer-campaign docstring warnings outside this feature's scope.
