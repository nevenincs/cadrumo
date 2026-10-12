---
tags:
  - '#exec'
  - '#live-agent-evaluation'
date: '2026-10-12'
modified: '2026-10-12'
body_schema: 'body-v2'
body_hash: 'sha256:e949daf21f01c9e848bd9390700d5b5dc84f9dc9775791d3791bddb7ebe57949'
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
- `S04` `A` `dev/agent_eval/live/scenario.py`
- `S04` `A` `dev/agent_eval/live/scenarios/modelo_130_dr130.toml`
- `S04` `A` `dev/agent_eval/live/scenarios/modelo_303_quarter.toml`
- `S04` `A` `dev/agent_eval/tests/test_live_scenarios.py`
- `S04` `verify:` `pytest dev/agent_eval/tests/test_live_scenarios.py` -> `pass`
- `S04` `verify:` `ruff check, ruff format, ty check on touched files` -> `pass`
- `S05` `A` `dev/agent_eval/live/drivers.py`
- `S05` `A` `dev/agent_eval/live/recorder.py`
- `S05` `A` `dev/agent_eval/tests/test_live_recorder.py`
- `S05` `verify:` `pytest dev/agent_eval/tests/test_live_recorder.py` -> `pass`
- `S05` `verify:` `ruff check, ruff format, ty check on touched files` -> `pass`
- `S05` `verify:` `real packaged MCP session on an isolated root: tool list read, pre-P10 surface flagged as product findings (sign-in tools, secret arguments), scripted client refused authentication_required with no sign-in` -> `pass`
- `S06` `A` `dev/agent_eval/live/capture.py`
- `S06` `A` `dev/agent_eval/tests/test_live_capture.py`
- `S06` `verify:` `pytest dev/agent_eval/tests/test_live_capture.py` -> `pass`
- `S06` `verify:` `ruff check, ruff format, ty check on touched files` -> `pass`

## Notes

- `S02` import gate failed on findings outside this Step: P10 removing `cadrumo_harness.mcp` `held_secrets,` `session_acts` and `installation_acts` while the gate ran, and stale load-target metadata; no finding names `dev/agent_eval`
- `S05` the API and claude CLI drivers were not run against a signed-in profile: this SSH logon's credential store refuses stored sign-in; that live run is S11
- `S06` committed after S05, whose recorder imports this scrubber; the S05 commit alone does not import cleanly
