---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S176'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Build Sphinx with warnings as errors and verify references, tree, links, and sequences

## Scope

- `dev/docs/tests/test_docs_build.py`

## Description

- Build Sphinx with warnings as errors and verify references, tree, links, and sequences.

## Outcome

The nitpicky warnings-as-errors docs-build gate is green. It builds the
documentation in a subprocess under the `-W` policy and asserts references
resolve, the generated CLI and API trees build, cross-links land, and sequences
render, so a broken reference or an unresolved anchor fails the build rather than
shipping. Green.

The run covers the four coordinator-authored how-to pages changed during this
assignment: the page commits `d53a0f0556` (protect-data-access, quarantine
route), `644cb2f30e` (index lock/switch retirement and ledger-evidence
attach-versus-link), and `19ab62dc0e` (profile-setup export-versus-SAR-versus-
sealed-archive) are all ancestors of the build HEAD, confirmed by
`git merge-base --is-ancestor`. So the warnings-as-errors build validated the
authored prose as it stands at HEAD, not a pre-edit copy.

Command: `uv run --no-sync pytest -p no:cacheprovider -n0 -m "unit or integration"
-o addopts="" dev/docs/tests/test_docs_build.py`. Collected 17, `17 passed in
36.35s`, exit code 0, at HEAD `541e73b457085d2cbb7247642ba7160cfdf12b64`.

## Notes

The gate carries a 1800-second budget, but this run completed in 37 seconds: the
roughly 840-second single-worker page-render sweep the coordinator warned about
lives in a different module (`test_built_site_resolvability_sweep.py`), not in
this build gate, so no long lane held this Step. Same peer core-import block
delayed the initial start; not touched, cleared on the peer's landing.
