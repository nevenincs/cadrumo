# Testing lanes and the local gate

Tests are selected by where they live and by which recipe names them, never by how long they take. A lane is a `just` recipe that fixes a marker expression, a path set and a parallel or serial pass. The full local gate, `just gate-local`, runs every lane and static check once as a graph of concurrent steps and keeps a record of the run. Use the narrowest lane that covers a change while developing, and the gate only to prove a named head.

## Choosing what to run

| Situation | Run |
|---|---|
| Editing one module | `uv run --no-sync pytest <file> -n 0` (or `-n 2`); nothing wider until it passes |
| One product area | `just test-cli`, `just test-tui`, `just test-calculations` |
| Registry data or compiler | `just check-registry-gate`, then `just test-registry` |
| Before handing work over | `just check-code`, `just check-registry-gate`, `just test-gate`, then read `just report-code-health` |
| Tooling under `dev/` | `just test-test-policy`, `just test-repository-contracts`, `just test-ci-contracts-gate` |
| Documentation | `just docs-page PATH` for one page; `just docs-check` for the blocking checks |
| Proving a head | `just gate-local <head label>` on a quiet machine and a still tree |

`just test-gate` is the change-scoped gate: `dev.ci.change_scope` maps changed paths to test targets, and a change it cannot narrow runs a fixed contract set behind a banner. It is quicker than the full gate and proves less.

## How lanes are built

- **Markers.** Every test is `unit` or `integration`. `serial` marks a test that reads or changes process-global state and must run with `-n0`. `perf`, `external_tool`, `os_keychain`, `windows_only`, `native_package`, `resident_service`, `private_ingest_corpus`, `google_publisher_client` and `aeat_live` are opt-in and held out of every portable lane; each has its own recipe ([markers](../../../../pyproject.toml#L1238)).
- **Default selection.** A bare `pytest` selects `unit` under the declared `testpaths`, which cover the product source roots only. Tests under `dev/` and `native/tests` run only through recipes that restate the markers ([addopts](../../../../pyproject.toml#L1221)).
- **Parallel and serial are separate verdicts.** A lane with both has a `-parallel` and a `-serial` recipe, and the aggregate runs one then the other. Never fold the serial tests into the parallel pass to save time.
- **Workers.** Lanes use xdist with `--dist=loadfile`, so one file runs on one worker from start to finish. The worker count is six unless `CADRUMO_PYTEST_WORKERS` is set; the default is a recorded decision and is not changed to speed a run up. A recipe or the gate may pass an explicit count ([worker hook](../../../../src/cadrumo/tests/worker_count_hook.py#L67)).
- **No runtime-cost marker.** There is no `slow` marker, no scheduled tier and no time limit on a correctness test. A test that is too slow is made faster or split; it is not moved out of the gate.
- **Reachability.** A test that no lane selects fails `dev/tests/test_lane_reachability.py`, so a new `tests/` directory needs a lane path. Changing which recipe owns a population means updating the canonical population set in that test ([reachability](../../../../dev/tests/test_lane_reachability.py)).
- **Reports and logs.** With `CADRUMO_CI_REPORTS_DIR` set, each pytest run writes a JUnit file there; every run also writes a log under `.tmp/logs/test-runs/` ([reports](../../../../dev/ci_reports.py), [run logging](../../../../dev/test_runs/logging.py)).

The aggregates are `test-product` (the sequence harness, then unit and integration), `test-registry` (collect and load, then calculations and conformance) and `test-tooling` (test-policy, repository contracts, CI contracts). `test-pytest-harness` runs the verification harness and the whole CLI sequence corpus outside any worker pool.

## The local gate

`just gate-local LABEL` runs `python -m dev.test_runs gate` over the graph in [dev/ci/gate-local.toml](../../../../dev/ci/gate-local.toml). `LABEL` names the tree in the record; pass the short head. The earlier body, eleven recipes one after another, remains as `just gate-local-sequential` ([recipe](../../../../justfile#L2200), [sequential](../../../../justfile#L2257)).

- **Graph.** Each `[[node]]` has a `name`, a `kind` (`prerequisite`, `static`, `build`, `pytest-parallel`, `pytest-serial`), a `command`, and optionally `weight`, `workers`, `after`, `exclusive` and `alone`. Node order in the file is start priority. Every population of the sequential gate is a node exactly once; `dev/ci/tests/test_gate_local_graph.py` proves that from the justfile, so adding or removing a gate population means changing both ([graph loader](../../../../dev/test_runs/gate_graph.py), [proof](../../../../dev/ci/tests/test_gate_local_graph.py)).
- **Budget.** Running nodes never exceed the budget in summed `weight`: 23 slots by default, or `CADRUMO_GATE_BUDGET`. A pytest node's `workers` reaches its child as `CADRUMO_PYTEST_WORKERS`. Weights are initial values meant to be tuned from gate records ([schedule](../../../../dev/test_runs/gate_schedule.py)).
- **Exclusive resources.** Nodes that write the same output never overlap: `authority` (`.authority/`), `fixtures`, `cmake` (the host preset's build tree), `docs-output` (`build/docs`) and `distributions`. `alone = true` runs a node with nothing else running; the CPU-budget benchmarks use it.
- **Prerequisites.** The authority is published first when stale. When a prerequisite fails, the nodes that depend on it are reported as not run, not as failed.
- **Record.** Each run writes `var/gate-runs/<UTC stamp>/` with `gate-record.json` (per-node verdict and wall time), `logs/<node>.log` and `reports/<node>/` JUnit files; `python -m dev.test_runs gate-timing --record-dir DIR` summarises it. A record whose status is still `running` is an interrupted run, not a verdict ([runner](../../../../dev/test_runs/gate_runner.py), [timing](../../../../dev/test_runs/gate_timing.py)).
- **Still tree.** The runner takes a content digest of the source tree at the start and at the end. If they differ the run is `invalid_tree_moved` and exits 7: nothing may be edited, landed or regenerated in the checkout during a gate. Other exits are 0 for pass, the first failing node's code for a failure and 130 for an interrupt.
- **Part of the gate.** `--only NODE` (repeatable) runs chosen nodes with their record, and `--dry-run` prints the schedule. Use these to check a graph change; they are not a gate verdict.

## Work the gate reuses

Reuse is always keyed by a content digest of declared inputs, never by modification time and never by version-control state. A missing or unreadable record means the full run.

- **Code-quality suite.** `dev.quality.suite` runs its checks side by side with `--jobs N` and, given `--verdict-dir`, skips a check whose inputs, tool version and configuration match a recorded clean verdict. Style, format, dependency declarations, frontend and Rust checks always run. Per-run variables are excluded from the key by name, so add any new per-run variable to that list or reuse never hits ([suite](../../../../dev/quality/suite.py), [verdicts](../../../../dev/quality/suite_verdicts.py)).
- **Compiled registry.** Test workers load the compiled bundled registry from a validated disk copy instead of compiling it each. The copy is allowed only for the immutable bundled root and is refused for any other registry root ([validated copy](../../../../dev/registry/compiler/validated_authority_copy.py)).
- **Documentation.** The gate makes one strict full build and records it; the strict-build test reads that record through `CADRUMO_DOCS_STRICT_BUILD_RECORD` instead of building again. Sequence goldens reuse a clean verdict per sequence; `CADRUMO_DOCS_SEQUENCE_JOBS` sizes the pool, `CADRUMO_DOCS_SKIP_SEQUENCE_CHECK=1` is for a build whose sequences another node checks, and `CADRUMO_DOCS_FORCE_SEQUENCE_CHECK` forces the check ([build record](../../../../dev/docs/strict_build_record.py), [sequence verdicts](../../../../dev/docs/sequences/verdict_cache.py)).
- **Persona worlds.** Profile and persona fixtures are built once per run through production operations, sealed, and copied per test; the seal carries a digest of the producing sources. Test processes never write fixtures ([sealed world](../../../../src/cadrumo/adapters/persistence/profile/tests/sealed_profile_world.py)).

## Working notes

- A gate is a whole-machine job of roughly an hour. Start it in the background, on a machine with no other heavy work and enough free memory, and tell anyone sharing the checkout to hold edits until it ends. A loaded machine turns timing-sensitive tests red and inflates every figure.
- Never use an attach profiler on a test process. Read timings from `--durations`, the JUnit files and the gate record.
- Stop only processes you started, identified by parent chain, never by name.
- A green result names a head: quote the label and the record directory. A failure on code you did not touch is reported, not fixed in passing.
- Generated inventories that gate changes touch: `just generate-import-load-targets` after adding, moving or removing a non-test module, and `just generate-operation-contract-manifest` after an operation schema change.
- Some gate-shard tests shell out to POSIX tools; on Windows they need Git's `usr\bin` on `PATH`.
- Observations to check against the current tree before relying on them: no full concurrent gate had been timed on a quiet machine when this was written, so the node weights are estimates; `just complexity-gate` is an absolute gate with no baseline and can fail on untouched code, which fails `check-code`; `just docs-check-prose` has been seen to scan no files and pass.
