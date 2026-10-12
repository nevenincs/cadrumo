---
tags:
  - '#exec'
  - '#live-agent-evaluation'
date: '2026-10-12'
modified: '2026-10-12'
body_schema: 'body-v2'
body_hash: 'sha256:2f5b94db913144eb3fb478416d778f93ee64b78c88b29f55564ea08d598112e0'
related:
  - "[[2026-10-12-live-agent-evaluation-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `live-agent-evaluation` ledger

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

- `S01` `M` `dev/agent_eval/__init__.py`
- `S01` `verify:` `ruff check dev/agent_eval/__init__.py` -> `pass`
- `S02` `A` `dev/agent_eval/live/__init__.py`
- `S02` `A` `dev/agent_eval/live/outcome.py`
- `S02` `A` `dev/agent_eval/live/package_copy.py`
- `S02` `A` `dev/agent_eval/tests/test_live_package_copy.py`
- `S02` `A` `dev/agent_eval/tests/test_live_outcome.py`
- `S02` `verify:` `pytest dev/agent_eval/tests/test_live_package_copy.py dev/agent_eval/tests/test_live_outcome.py` -> `pass`
- `S02` `verify:` `ruff check, ruff format, ty check on touched files` -> `pass`
- `S02` `verify:` `just check-import-boundaries` -> `fail`
- `S03` `A` `dev/agent_eval/live/package_host.py`
- `S03` `A` `dev/agent_eval/live/isolated_host.py`
- `S03` `A` `dev/agent_eval/tests/test_live_isolated_host.py`
- `S03` `verify:` `pytest dev/agent_eval/tests/test_live_isolated_host.py` -> `pass`
- `S03` `verify:` `ruff check, ruff format, ty check on touched files` -> `pass`
- `S03` `verify:` `real package smoke: verified copy of the rebuilt bundle, packaged runtime ready on a fresh root, profile created, sign-in classified credential_store_unavailable (config.login.session_not_persisted) on this SSH logon, run directory and processes removed` -> `pass`

## Notes

- `S02` import gate failed on findings outside this Step: P10 removing `cadrumo_harness.mcp` `held_secrets,` `session_acts` and `installation_acts` while the gate ran, and stale load-target metadata; no finding names `dev/agent_eval`
