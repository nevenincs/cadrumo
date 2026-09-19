---
tags:
  - '#research'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c663f58556acc585b160e1ed0806aed5145520c665d83f885560a20f2ed34a08'
related:
  - '[[2026-08-05-ci-lane-deconflation-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-27-canonical-release-pipeline-adr]]'
---
# `python-runtime-compatibility` research: `Python 3.13 and later compatibility evidence`

Cadrumo can use one source tree for CPython 3.13 and later, but the live checkout currently advertises more versions than CI proves and excludes 3.15 at the package boundary. The evidence favors an open-ended `>=3.13` installation floor, an explicit blocking matrix for released interpreters, an advisory-to-blocking prerelease lane for the next interpreter, and preservation of the exact 3.13.11 release-cohort build identity as a separate reproducibility concern.

## Findings

### Declared support and executed support disagree

The root declaration is `>=3.13,<3.15` and classifiers name 3.13 and 3.14, while the canonical local interpreter and every ordinary CI lane use 3.13.11; no workflow executes 3.14 or 3.15 (`pyproject.toml:6`, `pyproject.toml:20`, `pyproject.toml:21`, `.python-version:1`, `.github/workflows/ci.yml:169`, `.github/workflows/ci-full.yml:29`). Python 3.15 is currently RC2 and its final release is scheduled for 2026-10-01, so prerelease proof is possible now but a final-release claim cannot yet be evidenced. The ADR must separate released-version support from next-version readiness. https://peps.python.org/pep-0790/

### An open-ended floor needs a finite rolling evidence policy

Removing the speculative upper bound permits installation on later interpreters; it cannot prove compatibility with versions that do not yet exist. A credible policy blocks on every released interpreter from 3.13 through the current release, tests the next prerelease advisorially until an agreed promotion point, and adds classifiers only for blocking, tested releases. Keeping `<3.15` rejects the requested 3.15 runtime before resolution; replacing it with a moving ceiling would repeat that failure annually (`pyproject.toml:6`, `uv.lock:3`).

### The exact build interpreter is not the compatibility range

The immutable release cohort intentionally records and refuses any builder other than the exact `.python-version` value (`dev/packaging/release_cohort.py:51`, `dev/packaging/release_cohort.py:217`). Existing packaging workflow tests protect a single-build/same-bytes model, and the accepted installation-readiness decision requires tested cohort hashes rather than per-runtime rebuilds. Broadening this builder would weaken reproducibility. Runtime compatibility should instead install and exercise the same built wheel under each supported interpreter.

### A separate compatibility workflow avoids destabilizing protected lanes

The existing CI jobs have stable names and timing contracts, and the quick/release-cohort workflows deliberately reject matrix expansion (`.github/workflows/ci.yml:169`, `dev/packaging/tests/test_packaging_quick_workflow.py:48`, `dev/packaging/tests/test_packaging_smoke_workflow.py:61`). A dedicated workflow can execute 3.13.11, 3.14, and 3.15 prerelease/final without renaming protected checks or multiplying expensive cohort construction. The existing pin gate already permits a genuine matrix only when it contains the exact canonical pin, but does not require such a matrix (`dev/ci/tests/test_python_version_pin.py:33`).

### Release artifacts require runtime proof, not only source tests

The publish workflow already installs and smokes built artifacts across operating systems, but its matrix varies only by OS and inherits the single Python pin (`.github/workflows/publish.yml:70`, `.github/workflows/publish.yml:87`). Adding a Python dimension there would prove that the shipped bytes install and start across supported runtimes. A cheaper dedicated compatibility lane should catch source and dependency regressions before release, while release smoke remains the artifact-level authority.

### Packaging helpers contain both deliberate pins and accidental assumptions

`dev/packaging/runtime_wheelhouse.py:37` and `src/cadrumo_harness/_workspace.py:536` hard-code a 3.13 wheelhouse identity, while several smoke tools expose a Python selector that defaults from the running interpreter. The former must be classified before alteration: some values describe the canonical build channel, while marker environments used to resolve runtime dependencies should follow the selected target interpreter. Blanket replacement of every `3.13` literal would corrupt legitimate release identity.

### The source trees show focused compatibility risks rather than widespread obsolete APIs

A scan across `dev/` and `src/` found no production imports of PEP 594-removed modules, `distutils`, `imp`, legacy `importlib.resources` helpers, private `typing` classes, or deprecated asyncio policy functions. The main cross-version semantic risks are annotation introspection in `src/cadrumo/application/modelo/workspace_manifest.py:599` and dynamic `__annotations__` construction in `src/cadrumo/application/wizard/commands.py:1995`. The pervasive `from __future__ import annotations` remains supported by Python 3.15 and gives one string-annotation model across 3.13-3.15; removing it is not required for compatibility. https://docs.python.org/3.15/reference/simple_stmts.html#future-statements

### Compatibility must include dependencies and warnings

The lock mirrors the root Python ceiling and must be regenerated through uv after metadata changes (`uv.lock:3`). Resolution alone is insufficient: each matrix runtime should perform frozen synchronization or an isolated package install, import/CLI smoke, focused annotation contracts, and tests with deprecations promoted to errors where third-party noise can be separately attributed. Native-wheel availability must be observed per runtime; absence is a dependency blocker, not grounds to silently skip a supported row.

### Companion metadata should agree with the root claim

Both companion distributions already declare `>=3.13`, but only classify Python 3.13 (`packaging/cadrumo_data_manuals/pyproject.toml:16`, `packaging/cadrumo_data_manuals/pyproject.toml:30`, `packaging/cadrumo_data_official/pyproject.toml:16`, `packaging/cadrumo_data_official/pyproject.toml:30`). Because the root package requires those exact-version companions, their support classifiers and installation proof should move with the root compatibility claim.

### Existing concurrent work constrains implementation

The checkout contains unresolved and unrelated changes in workflows, `pyproject.toml`, `uv.lock`, and multiple `src/` files. Implementation must re-read every target and preserve those edits; the compatibility workflow is the lowest-overlap new surface. The stale comment at `dev/audit/security.py:54` still describes the former `<3.14` ceiling and should derive its reasoning from the live open-ended floor rather than being advanced to another soon-stale ceiling.

## Sources

- `pyproject.toml:6`
- `pyproject.toml:20`
- `pyproject.toml:21`
- `.python-version:1`
- `uv.lock:3`
- `.github/workflows/ci.yml:169`
- `.github/workflows/ci-full.yml:29`
- `.github/workflows/publish.yml:70`
- `.github/workflows/publish.yml:87`
- `dev/ci/tests/test_python_version_pin.py:33`
- `dev/packaging/release_cohort.py:51`
- `dev/packaging/release_cohort.py:217`
- `dev/packaging/runtime_wheelhouse.py:37`
- `dev/packaging/tests/test_packaging_quick_workflow.py:48`
- `dev/packaging/tests/test_packaging_smoke_workflow.py:61`
- `dev/audit/security.py:54`
- `src/cadrumo_harness/_workspace.py:536`
- `src/cadrumo/application/modelo/workspace_manifest.py:599`
- `src/cadrumo/application/wizard/commands.py:1995`
- `packaging/cadrumo_data_manuals/pyproject.toml:16`
- `packaging/cadrumo_data_manuals/pyproject.toml:30`
- `packaging/cadrumo_data_official/pyproject.toml:16`
- `packaging/cadrumo_data_official/pyproject.toml:30`
- https://peps.python.org/pep-0790/
- https://docs.python.org/3.15/reference/simple_stmts.html#future-statements
