---
tags:
  - '#exec'
  - '#package-verification'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:72b47c72ecced8f368fb10cfa9ee365c378158dca84c12d804e126c150807f61'
related:
  - "[[2026-10-13-package-verification-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `package-verification` ledger

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

- `S01` `D` `dev/quality/shard.py`
- `S01` `D` `dev/quality/tests/test_shard.py`
- `S01` `M` `pyproject.toml`
- `S01` `M` `dev/quality/metadata/import_load_targets.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S01` `M` `dev/audit/tests/test_unreachable_code_scan.py`
- `S01` `M` `dev/audit/tests/test_duplication_scan.py`
- `S01` `M` `dev/audit/tests/test_dead_code_scan.py`
- `S01` `M` `src/cadrumo/tests/test_dev_dotenv_bridge.py`
- `S01` `verify:` `just check-import-boundaries` -> `pass`
- `S01` `verify:` `ruff check` -> `pass`
- `S01` `verify:` `dev/tests/test_lane_reachability.py` -> `fail`
- `S01` `A` `dev/ci/lane_ctest_commands.py`
- `S01` `M` `dev/ci/lane_reachability.py`
- `S01` `M` `dev/tests/test_lane_reachability.py`
- `S01` `M` `dev/tests/test_dev_cli_justfile_wiring.py`
- `S01` `M` `justfile`
- `S01` `verify:` `dev/tests/test_lane_reachability.py` -> `pass`
- `S01` `verify:` `dev/tests/test_dev_cli_justfile_wiring.py` -> `pass`
- `S04` `D` `native/desktop/src-tauri/src/agent/direct.rs`
- `S04` `M` `native/desktop/src-tauri/src/agent/mod.rs`
- `S04` `M` `native/desktop/src-tauri/src/agent/supervisor.rs`
- `S04` `M` `native/desktop/src-tauri/Cargo.toml`
- `S04` `M` `dev/desktop_agent_live/lane.py`
- `S04` `verify:` `native/desktop/tests/run-backend.ps1 -Mode Unit -Filter agent` -> `pass`
- `S04` `verify:` `native/desktop/tests/run-backend.ps1 -Mode Clippy` -> `pass`
- `S04` `verify:` `ruff check dev/desktop_agent_live` -> `pass`
- `S03` `M` `dev/runtime_lifecycle/agent_live.py`
- `S03` `M` `dev/runtime_lifecycle/tests/test_agent_live.py`
- `S03` `verify:` `dev/runtime_lifecycle/tests/test_agent_live.py` -> `pass`
- `S03` `verify:` `ruff check` -> `pass`
- `S03` `verify:` `ty check` -> `pass`
- `S02` `M` `native/cmake/Packaging.cmake`
- `S02` `A` `native/tests/environment_launch_probe.py`
- `S03` `verify:` `dev/runtime_lifecycle/tests/test_agent_live.py` -> `pass`
- `S03` `by:` `vaultspec-standard-executor`
- `S04` `A` `dev/desktop_agent_live/tests/test_lane.py`
- `S04` `verify:` `dev/desktop_agent_live/tests` -> `pass`
- `S04` `by:` `vaultspec-standard-executor`

## Notes

- `S01` lane-reachability and justfile-wiring failures are pre-existing: unenrolled `dev/desktop_agent_live,` `dev/agent_eval/live` and other sessions' new tests; none involve S01 paths. dev/audit semantic, `semantic_duplication,` `legal_attribution_screen,` `legal_excerpt_vintage_screen` and `registry_temporal_range_sweep` kept as live gates or documented tools
- `S01` owner asked to fix the pre-existing census failures: CTest's package pytest suite is now a lane of test-native-bundle; orphan test paths enrolled in their capability lanes
- `S04` built in an isolated scratch build root and cargo target; the live desktop lane itself waits on the hosted proof and a built package with the agent image
- `S03` person side and file exchange built to the protocol agreed with CADRUMO-AGENT-CODE; step stays open until verify-agent-live passes against a staged package with the agent package runner
- `S02` covered by the canonical-environment plan's P04.S14 (73f13535cd, authored by tui-ee): CTest bundle.environment-launch starts bin/cadrumo-agent the way the runtime does and requires `hosted_tool_server_unproven` now, `agent_ready` once proofs exist; it has not yet run against a staged package
- `S03` relay calls are matched by their bare registry names, as CADRUMO-AGENT-CODE verified on the claude/api lane
- `S03` each receipt permission's gateway-recorded decision must also equal the answer given
- `S03` a run is judged only when its receipt lane is claude/api, the one lane that mounts the relay
- `S03` the claude/api-only lane check is withdrawn: the owner rules that every provider lane mounts the relay
- `S03` relayed calls are recognised by the agent's trusted `tool_server` and the bare registry name, on every provider lane
- `S03` an offered `allow_session` option never replaces the per-call `allow_once` answer
- `S03` owner ruling 2026-10-14: no hard-coded agent capability; the tool-name list is removed and each request is approved once, the run judged by outcome
- `S04` owner ruling 2026-10-14: the lane takes --provider and constructs `CADRUMO_LLM_<ID>_API_KEY;` no provider is named
