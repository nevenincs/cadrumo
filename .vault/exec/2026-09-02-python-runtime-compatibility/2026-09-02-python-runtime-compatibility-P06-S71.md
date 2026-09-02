---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:1d2c99fde3aaa918066ac207ddf459bca417d464c1bb5680bcffbea9f7674016'
step_id: 'S71'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Build and validate runtime-specific sealed wheelhouses for every blocking CPython minor

## Scope

- `dev/packaging/runtime_wheelhouse.py`
- `dev/packaging/python_cohort.py`
- `dev/ci/python_runtime_compatibility.py`

## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

- `M` `dev/ci/python_runtime_compatibility.py`
- `M` `dev/ci/tests/test_python_runtime_compatibility.py`
- `M` `dev/packaging/python_cohort.py`
- `M` `dev/packaging/runtime_wheelhouse.py`
- `M` `dev/packaging/tests/_cohort_attestation.py`
- `M` `dev/packaging/tests/test_acquire_tooling.py`
- `A` `dev/packaging/tests/test_runtime_wheelhouse.py`
- `M` `dev/packaging/tests/test_python_cohort_digest_assertions.py`
- `M` `src/cadrumo_harness/_workspace.py`
- `M` `src/cadrumo_harness/tests/_plugin_cohort.py`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility.py dev/packaging/tests/test_runtime_wheelhouse.py -o addopts=''` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility.py dev/packaging/tests/test_python_cohort.py src/cadrumo_harness/tests/test_plugin_workspace.py -o addopts=''` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/ci/python_runtime_compatibility.py dev/packaging/runtime_wheelhouse.py dev/packaging/python_cohort.py dev/packaging/tests/test_runtime_wheelhouse.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.packaging.release_cohort verify --cohort-dir var/python-runtime-wheelhouse-snapshot-0c9e915444e8/var/release-cohort-python-313-314-sealed` -> `pass`
- `verify:` `binary probes CPython 3.13.14 and 3.14.6, offline/no-index/find-links/require-hashes` -> `pass`

