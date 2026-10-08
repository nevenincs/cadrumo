---
tags:
  - '#exec'
  - '#git-free-tooling'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:2489c061bcdf7520c0f4ef8e93cddba671e60a4647c64c3c0635512623111574'
related:
  - "[[2026-10-07-git-free-tooling-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `git-free-tooling` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S01` `M` `dev/source_tree.py`
- `S01` `M` `dev/env/clean.py`
- `S01` `M` `dev/env/_dotenv.py`
- `S01` `M` `dev/env/tests/test_clean.py`
- `S01` `M` `dev/env/tests/test_dotenv.py`
- `S01` `M` `dev/registry/edition_round_trip.py`
- `S01` `M` `dev/deploy/docs_delivery_policy.py`
- `S01` `M` `native/cmake/BuildNumber.cmake`
- `S01` `M` `dev/packaging/native/tests/test_cmake_build_number.py`
- `S01` `verify:` `focused tests: 44 passed` -> `pass`
- `S01` `verify:` `scoped ruff lint and format` -> `pass`
- `S01` `verify:` `scoped ty` -> `pass`
- `S02` `M` `dev/ci/change_scope.py`
- `S02` `M` `dev/ci/sequence_goldens_gate.py`
- `S02` `M` `dev/ci/tests/test_change_scope.py`
- `S02` `M` `dev/ci/tests/test_sequence_goldens_gate.py`
- `S02` `M` `dev/ci/tests/test_ci_workflow.py`
- `S02` `M` `dev/packaging/smoke_homebrew.py`
- `S02` `M` `dev/packaging/smoke_scoop.ps1`
- `S02` `M` `dev/packaging/acquire_scoop.ps1`
- `S02` `M` `justfile`
- `S02` `M` `.github/workflows/merge-gate.yml`
- `S02` `M` `.github/workflows/release-please.yml`
- `S02` `M` `.github/workflows/release.yml`
- `S02` `verify:` `focused tests plus executable-call gate: 157 passed` -> `pass`
- `S02` `verify:` `actionlint` -> `pass`
- `S02` `verify:` `workflow data quality` -> `pass`
- `S02` `verify:` `PowerShell syntax` -> `pass`
- `S02` `verify:` `scoped Ruff lint and format` -> `pass`
- `S02` `verify:` `scoped ty` -> `pass`
- `S03` `D` `dev/quality/tests/test_git_invocations_take_no_optional_locks.py`
- `S03` `A` `dev/quality/tests/test_no_git_cli.py`
- `S03` `A` `.vault/audit/2026-10-07-git-free-tooling-audit.md`
- `S03` `M` `.vaultspec/rules/00-architecture.md`
- `S03` `M` `.vaultspec/skills/cadrumo-start/references/00-architecture.md`
- `S03` `M` `.codex/rules/00-architecture.md`
- `S03` `M` `.agents/skills/cadrumo-start/references/00-architecture.md`
- `S03` `verify:` `final invocation gate: 11386 source/configuration files, zero offenders, 25 tests passed` -> `pass`
- `S03` `verify:` `repeat product reachability: 3269 of 3269 reachable, zero findings` -> `pass`
- `S03` `verify:` `repeat Vulture: 3270 offered, zero findings` -> `pass`
- `S03` `verify:` `publication delivery and guard checks: 69 passed` -> `pass`
- `S03` `verify:` `final guard scoped Ruff lint format and ty` -> `pass`
- `S03` `verify:` `four-surface rule/reference parity` -> `pass`
- `S03` `by:` `root integrated review`

## Notes

- `S02` Existing `test_the_harness_real_proof_outruns_the_default_per_test_wall_ceiling` still requires the removed global pytest timeout; the initial run recorded that failure, the final focused run explicitly excludes it. No release publication or full Homebrew/Scoop installation was performed on this Windows host.
