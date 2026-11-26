# Testing lanes and the local gate

Tests are selected by where they live, by the markers their module declares and by which recipe names them, never by how long they take. A lane is a `just` recipe that fixes a marker expression, a path set and a parallel or serial pass. The full local gate, `just gate-local`, runs every lane and static check once as a graph of concurrent steps and keeps a record. Use the narrowest thing that covers a change while developing, and the gate only to prove a named head.

## Choosing what to run

| Situation | Run |
|---|---|
| One unit test file | `uv run --no-sync pytest <file> -n 0` |
| One integration file | `uv run --no-sync pytest <file> -n 0 -m integration` |
| One serial file or test | `uv run --no-sync pytest <file> -n 0 -m "integration and serial"` (use the file's own execution marker) |
| One product area | `just test-cli`, `just test-tui`, `just test-calculations` |
| Registry data or compiler | `just check-registry-gate`, then `just test-registry` |
| Tooling under `dev/` | `just test-test-policy`, `just test-repository-contracts`, `just test-ci-contracts-gate` |
| Documentation | `just docs-page PATH` for one page; `just docs-check` for the blocking checks |
| Before handing work over | `just check-code` (or `just check-python` without the native tools), `just check-registry-gate`, `just test-gate [MANIFEST]`, then read `just report-code-health` |
| Proving a head | `just gate-local <head label>` on a quiet machine and a still tree |

Before any of these, a stale derived input makes the result meaningless: see [authority and fixture staleness](dev-authority-and-fixture-staleness.md) and [generated artefacts](dev-generated-artefacts.md).

## What a bare pytest run does

The configured options apply to every invocation: xdist with `-n auto --dist=loadfile`, the marker expression `unit and not perf and not external_tool and not os_keychain and not windows_only and not resident_service and not private_ingest_corpus and not google_publisher_client`, strict markers and configuration, plain assertions, and the run-logging plugin ([addopts](../../../../pyproject.toml#L1221)).

- **Integration tests are deselected** unless you pass `-m`. A file that "ran" with everything deselected has proved nothing; read the summary line.
- **`-n auto` means six workers**, or `CADRUMO_PYTEST_WORKERS` when set; an explicit `-n N` wins. Use `-n 0` for one file: worker start-up costs more than it saves ([worker hook](../../../../src/cadrumo/tests/worker_count_hook.py#L67)).
- **A `serial` test under workers is held out and the session ends with an error**, so a serial test never silently runs in parallel. Run it with `-n 0` ([serial hold](../../../../src/cadrumo/tests/marker_hook.py#L301)).
- **`testpaths` cover the product source roots only.** Tests under `dev/` and `native/tests` run when you name the path or use a recipe that does.
- **Every run writes a log** in a per-invocation folder under `.tmp/logs/test-runs/` and prints its path at the end of the run. `CADRUMO_TEST_LOG_ROOT` moves the base. With `CADRUMO_CI_REPORTS_DIR` set, a JUnit file is written there too ([run logging](../../../../dev/test_runs/logging.py), [reports](../../../../dev/ci_reports.py)).

## Markers and placement

- Tests live in the narrowest owning `tests/` directory, in files named `test_*.py`; a test file beside a production module is not allowed ([test conventions](../../../../src/cadrumo/tests/README.md)).
- **Every test module declares its markers itself**, for example `pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]`. Nothing applies `unit` by default. Collection refuses a test without exactly one execution marker (`unit`, `integration` or `aeat_live`) and exactly one accepted `hex_*` layer marker ([marker contract](../../../../src/cadrumo/tests/marker_hook.py#L171)).
- `serial` rides beside the execution marker and may be set per class or function. It marks a test that reads or changes process-global state.
- `perf`, `external_tool`, `os_keychain`, `windows_only`, `resident_service`, `private_ingest_corpus`, `google_publisher_client` and `aeat_live` are opt-in and held out of every portable lane; each has its own recipe. `native_package` marks tests whose subject is an executable staged by the native build; they are selected through the CTest lane `just test-native-live` ([markers](../../../../pyproject.toml#L1238)).
- A misspelt or retired marker fails collection.
- **Reachability.** A test that no lane selects fails `dev/tests/test_lane_reachability.py`, and a module with no execution marker fails `src/cadrumo/tests/test_every_test_module_is_lane_reachable.py`. A new `tests/` directory outside the existing lane paths needs a lane path; changing which recipe owns a population means updating the canonical population set in the reachability test ([reachability](../../../../dev/tests/test_lane_reachability.py)).

## The lanes

| Recipe | Selects |
|---|---|
| `test-unit` | `unit` over the product roots, with the harness files and calculation paths held out |
| `test-cli` | `src/cadrumo/entrypoints/cli`, parallel pass then serial pass |
| `test-tui` | `src/cadrumo/entrypoints/tui`, `dev/tui/tests` and the TUI launcher test, parallel then serial |
| `test-calculations` | `src/cadrumo/application/calculations` and `src/cadrumo/domain/calculations/registry/tests`, parallel then serial |
| `test-integration` | `test-integration-parallel` (`integration and not serial`) then `test-integration-serial` (`integration and serial`, `-n0`) |
| `test-pytest-harness` | The worker-count harness and the whole CLI sequence corpus, `-n0`, with a collect-only pass first |
| `test-product` | `test-pytest-harness`, then the unit and integration populations |
| `test-registry` | Publishes the authority when stale; collect, source load, calculations, then conformance |
| `test-tooling` | `test-test-policy`, `test-repository-contracts`, `test-ci-contracts` (the deterministic set `test-ci-contracts-gate`, then the CPU-budget pass `test-ci-perf`) |
| `test-smoke` | One end-to-end installed-CLI journey |
| `test-coverage` | The default unit selection with a coverage floor |

Rules that hold across all of them:

- **Parallel and serial are separate verdicts.** A lane with both has a `-parallel` and a `-serial` recipe. An empty serial pass is tolerated; folding serial tests into the parallel pass is not.
- **One file, one worker.** With `--dist=loadfile` a long file occupies one worker from start to finish, so a very long file sets the tail of its lane whatever the worker count.
- **The worker default is a recorded decision.** Do not change it to speed a run up; a recipe or the gate may pass an explicit count.
- **No runtime-cost marker.** There is no `slow` marker, no scheduled tier and no time limit on a correctness test. A test that is too slow is made faster or split; it is not moved out of the gate.

## The change-scoped gate

`just test-gate [MANIFEST]` takes the path of a file holding one repository-relative changed path per line. The recipe never asks version control for the changes: build the manifest yourself. With no argument it scopes the full tree.

`dev.ci.change_scope` selects the `tests/` directory of the nearest owning ancestor of each changed source file and of its direct importers. When the change cannot be narrowed (more than 40 targets, a change under `cadrumo.core`, a Python file with no owning tests, a `conftest.py`, `pyproject.toml` or `uv.lock`), it runs only a fixed contract set and prints a "CHANGE SCOPE TOO BROAD" banner: that result is weaker than it looks, and the affected lanes should be run by name. The recipe ends with `test-pytest-harness`. `just test-gate-plan` prints the shard matrix and `just test-gate-shard INDEX/COUNT` runs one shard ([scope](../../../../dev/ci/change_scope.py#L59), [recipe](../../../../justfile#L1421)).

## The full local gate

`just gate-local LABEL` runs `python -m dev.test_runs gate` over the graph in [dev/ci/gate-local.toml](../../../../dev/ci/gate-local.toml). `LABEL` names the tree in the record; pass the short head. The earlier body, eleven recipes one after another, remains as `just gate-local-sequential` ([recipe](../../../../justfile#L2200), [sequential](../../../../justfile#L2257)).

- **Graph.** Each `[[node]]` has a `name`, a `kind` (`prerequisite`, `static`, `build`, `pytest-parallel`, `pytest-serial`), a `command`, and optionally `weight`, `workers`, `after`, `exclusive` and `alone`. Node order in the file is start priority. Every population of the sequential gate is a node exactly once; `dev/ci/tests/test_gate_local_graph.py` proves that from the justfile, so adding or removing a gate population means changing both ([graph loader](../../../../dev/test_runs/gate_graph.py), [proof](../../../../dev/ci/tests/test_gate_local_graph.py)).
- **Budget.** Running nodes never exceed the budget in summed `weight`: 23 slots by default, or `CADRUMO_GATE_BUDGET`. A pytest node's `workers` reaches its child as `CADRUMO_PYTEST_WORKERS`. Weights are initial values meant to be tuned from gate records ([schedule](../../../../dev/test_runs/gate_schedule.py)).
- **Exclusive resources.** Nodes that write the same output never overlap: `authority` (`.authority/`), `fixtures`, `cmake` (the host preset's build tree), `docs-output` (`build/docs`) and `distributions`. `alone = true` runs a node with nothing else running; the CPU-budget benchmarks use it.
- **Prerequisites.** The authority is published first when stale. When a prerequisite fails, the nodes that depend on it are reported as not run, not as failed.
- **Record.** Each run writes `var/gate-runs/<UTC stamp>/` with `gate-record.json` (per-node verdict and wall time), `logs/<node>.log` and `reports/<node>/` JUnit files; `python -m dev.test_runs gate-timing --record-dir DIR` summarises it. A record whose status is still `running` is an interrupted run, not a verdict ([runner](../../../../dev/test_runs/gate_runner.py), [timing](../../../../dev/test_runs/gate_timing.py)).
- **Still tree.** The runner takes a content digest of the source tree at the start and at the end. If they differ the run is `invalid_tree_moved` and exits 7: nothing may be edited, landed or regenerated in the checkout during a gate. Other exits are 0 for pass, the first failing node's code for a failure and 130 for an interrupt.
- **Part of the gate.** `--only NODE` (repeatable) runs chosen nodes with their record, and `--dry-run` prints the schedule. Use these to check a graph change or to rerun one red node; they are not a gate verdict.

## Work the gate reuses

Reuse is always keyed by a content digest of declared inputs, never by modification time and never by version-control state. A missing or unreadable record means the full run.

- **Code-quality suite.** `dev.quality.suite` runs its checks side by side with `--jobs N` and, given `--verdict-dir`, skips a check whose inputs, tool version and configuration match a recorded clean verdict. Style, format, dependency declarations, frontend and Rust checks always run. Per-run variables are excluded from the key by name, so add any new per-run variable to that list or reuse never hits ([suite](../../../../dev/quality/suite.py), [verdicts](../../../../dev/quality/suite_verdicts.py)).
- **Compiled registry.** Test workers load the compiled bundled registry from a validated disk copy instead of compiling it each ([validated copy](../../../../dev/registry/compiler/validated_authority_copy.py)).
- **Documentation.** The gate makes one strict full build and records it; the strict-build test reads that record through `CADRUMO_DOCS_STRICT_BUILD_RECORD` instead of building again. Sequence goldens reuse a clean verdict per sequence; `CADRUMO_DOCS_SEQUENCE_JOBS` sizes the pool, `CADRUMO_DOCS_SKIP_SEQUENCE_CHECK=1` is for a build whose sequences another node checks, and `CADRUMO_DOCS_FORCE_SEQUENCE_CHECK` forces the check ([build record](../../../../dev/docs/strict_build_record.py), [sequence verdicts](../../../../dev/docs/sequences/verdict_cache.py)).
- **Persona worlds.** Profile and persona fixtures are built once per run through production operations, sealed, and copied per test; the seal carries a digest of the producing sources ([sealed world](../../../../src/cadrumo/adapters/persistence/profile/tests/sealed_profile_world.py)).

## Working notes

- A gate is a whole-machine job of roughly an hour. Start it in the background, on a machine with no other heavy work and enough free memory, and tell anyone sharing the checkout to hold edits until it ends. A loaded machine turns timing-sensitive tests red and inflates every figure.
- When one node is red, read `logs/<node>.log`, fix, and rerun that node's recipe or `--only NODE` before spending another full gate.
- Never use an attach profiler on a test process. Read timings from `--durations`, the JUnit files and the gate record.
- Stop only processes you started, identified by parent chain, never by name.
- A green result names a head: quote the label and the record directory. A failure on code you did not touch is reported, not fixed in passing.
- Some gate-shard tests shell out to POSIX tools; on Windows they need Git's `usr\bin` on `PATH`.
- Observations to check against the current tree before relying on them: no full concurrent gate had been timed on a quiet machine when this was written, so the node weights are estimates; `just complexity-gate` is an absolute gate with no baseline and can fail on untouched code, which fails `check-code`; `just docs-check-prose` has been seen to scan no files and pass.
