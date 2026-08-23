---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:bedcf56916ba1ab0fa3618f2a4d43de936b6185ca01302707ed8b6be884e28e9'
step_id: 'S60'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Physically delete the entire embedded external-client harness workspace and Python package, including every module, skill, rule, server entrypoint, fixture, test, build record, workspace member, lock entry, alias, re-export, shim, and fallback

## Scope

- `src/cadrumo-harness/`
- `pyproject.toml`
- `and uv.lock`

## Description

- Validate that the recursive deletion target resolves exactly to `Y:\code\aeat-worktrees\main\src\cadrumo-harness` and remains inside the workspace source root.
- Delete the complete embedded client distribution: 157 tracked files spanning its project record, modules, operating skills and rules, server entrypoints, fixtures, and tests.
- Remove the empty directory skeleton left after the tracked files disappeared and verify that the physical root no longer exists.
- Remove the distribution's uv source, workspace membership, development dependency, lint exceptions, and default test-path enrollment from `pyproject.toml`.
- Remove the workspace member, root development dependency edges, editable source, package metadata, and dependency records from `uv.lock`.
- Validate the exact staged tree through a Git archive, locked resolution/export, real base wheel build, scoped tests, dependency-surface inspection, and clean installed-environment reconciliation.

## Outcome

The embedded client package is absent from the tracked tree, filesystem, lock graph, base project configuration, active environment metadata, and Python import resolution. The S60 path slice of mixed commit `0a4c5377ef6` carries 157 files and 23,823 deleted lines under `src/cadrumo-harness/`; every deleted tracked file remains recoverable through Git. The final membership tranche contains no harness reference in either project configuration or lock data.

The isolated staged-tree proof reported no harness path or membership reference, a green `uv lock --check`, a locked base export with no harness dependency, and exactly one real `cadrumo-0.2.2-py3-none-any.whl` build. The scoped runtime gate passed 26 tests; the dependency-surface command reported a valid base graph. `uv sync --locked` then removed the stale editable installation, after which distribution discovery returned false and `find_spec("cadrumo_harness")` returned none.

## Notes

An uncontrolled shared writer prepared the deletion before this executor started, and mixed commit `0a4c5377ef6` consumed the complete tree while this Step was in progress. The whole commit contains 194 deleted paths and 31,696 deleted lines: the 157-path, 23,823-line S60 harness slice plus a premature 37-path, 7,873-line `dev/agent_eval/` slice assigned to S63. S60 claims only the path-scoped harness deletion, not commit purity or S63 completion. History was not rewritten or reverted; S63 remains open and must independently audit, complete, and record its already-landed payload. The remaining S60 code/configuration cleanup was staged separately as exactly `pyproject.toml` and `uv.lock`, with the S60 lifecycle records joining only at close.

A second uncontrolled shared-index collision consumed the final S60 membership and lifecycle tranche in mixed commit `2a77bbb4cc` before this executor's guarded commit could run. The whole commit contains nine paths with 95 insertions and 144 deletions. Its S60 slice contains exactly six paths with 12 insertions and 142 deletions: the S60 audit, Step record, feature index, corrected plan, `pyproject.toml`, and `uv.lock`. Its excluded S174 slice contains exactly three paths with 83 insertions and two deletions: the source-casilla S174 audit, Step record, and plan. S60 claims only the six-path slice, not commit purity or S174 completion. The guarded commit observed an empty index after the concurrent commit and aborted without creating a redundant commit; history was not rewritten.

Commit `b97a051f48` separately and prematurely deleted `dev/packaging/installed_mcp_oracle.py` and `dev/packaging/tests/test_installed_oracles.py`, which belong to S69. The adjacent removal of the now-stale `dev/packaging/tests/test_installed_oracles.py` default-test-path row remains deliberately outside S60's staged index because S69 and S73 own its lifecycle; both Steps remain open and must audit and record the landed deletion and residual configuration. The staged baseline also still names the deleted harness test in the `justfile` per-push enrollment and names the retired distribution in the Homebrew generator; those are explicit dependencies for S73 and S70 respectively. The external-client inverse gate retains its two marker literals intentionally. No surviving Python file is modified by S60, so Ruff and static typing have no scoped source target; lock, export, build, installed-runtime, and real test gates cover the changed boundary.
