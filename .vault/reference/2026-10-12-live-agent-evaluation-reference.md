---
tags:
  - '#reference'
  - '#live-agent-evaluation'
date: '2026-10-12'
modified: '2026-10-12'
body_schema: 'body-v2'
body_hash: 'sha256:6028466485913b02480405ad37149c1da3198f4e150e70a52e555827a7a47231'
related:
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - "[[2026-07-03-agent-harness-operability-followup-audit]]"
---

# `live-agent-evaluation` reference: `existing live-agent substrate, runtime hosts and lanes`

This record covers what the repository already owns for a live agent run, what the 2026-10-12 demonstration did outside it, and where each piece would come from. The evidence comes from reading the code at the cited locators and the staged package on this host on 2026-10-12. Every count is as of that date.

## Summary

### The R7 scoring substrate exists, but nothing drives it

- `dev/agent_eval/_models.py:618-743` defines these types:
  - `LiveToolCallRecord`, which holds the tool name, command key, arguments JSON, error flag, result text and duration.
  - `LiveNarrationRecord` and `LiveElicitationRecord`.
  - `LiveTrajectory` and `LiveInvariantVerdict`.
- `LIFECYCLE_STAGE_ORDER` (`_models.py:69-74`) is `modelo.work.create`, `.calculate`, `.verify`, `modelo.export`.
- `dev/agent_eval/_live_scoring.py:276-284` `score_live_trajectory` scores:
  - key resolution
  - lifecycle order
  - the scenario's expected trajectory, as an order-preserving subsequence (`:325`)
  - tool errors
  - narration faithfulness
- `_score_hard_invariants` (`:238-273`) holds the hard invariants. One fails on any call whose leaf is in a caller-supplied `live_write_leaves` set. The other fails on any blocked hand-off narration. The caller injects the faithfulness check (`:40-49`).
- `dev/agent_eval/_flywheel.py` promotes a failure into a golden scenario. `_replay.py` replays captured records, and `_report.py` renders a report.
- `LiveTrajectory` is used only by the package's own tests. No module spawns `claude`, uses the Agent SDK or calls the Anthropic API to drive MCP. Every `ClientSession` or `stdio_client` use is a scripted client: `dev/agent_eval/tests/test_installed_*_stdio.py`, `src/cadrumo_harness/mcp/tests/session.py:36` and `dev/runtime_lifecycle/client_probes.py:17-18`.
- The MCP `execute` tool takes a `definition_id` (`src/cadrumo_harness/mcp/protocol_contract.py:421`). The demonstration used `ledger.add`, `ledger.list`, `modelo.work.create`, `modelo.work.calculate`, `modelo.work.verify` and `modelo.export`. The lifecycle order uses the same keys, so observed calls map onto the scorer without a translation table.
- `dev/agent_eval/scenarios/*.toml` holds eight golden scenarios. `modelo_130.toml` (130, 2024, 1T) expects this trajectory:
  - `modelo.describe` and `modelo.casillas`
  - `modelo.work.create`, `.calculate`, `.revision` and `.verify`
  - `modelo.export`
  - `modelo.reconcile.pull`

  That last step is a remote read. A live run on an isolated root therefore cannot cover the trajectory as written, so a live scenario needs its own required subsequence.
- A Modelo 130 oracle exists that does not rely on the code under test. `dev/agent_eval/tests/test_modelo_130_value_oracle.py:1-45` feeds the AEAT DR 130 worked example through the registry engine: ingresos 12.000 and gastos 4.000 give casillas 04 and 07 of 1.600.

### The `dev/agent_eval` import boundary is only stated in a docstring

- `dev/agent_eval/__init__.py:12-21` says the package imports only `cadrumo.core` from the product. No import-linter contract enforces this.
  - The only contract that names the package is `closed-dev-classification` (`.importlinter:35-41`). It gives each `dev` subpackage a declared lane.
  - No contract limits what `dev` may import from `src`.
  - `src` and `cadrumo_harness` are forbidden from importing `dev` (`.importlinter:59-68`, `:147-156`).
- The docstring is already wrong:
  - `dev/agent_eval/_action_coverage.py:15-23` and `:174-176` import application and entrypoint modules.
  - So do `_runner.py:78-79` and `_models.py:63`.
  - `dev/agent_eval/tests/` imports adapters, application modules and `cadrumo_harness` freely.

### How the repository starts a real runtime

- **From current source, launched directly.** `src/cadrumo/entrypoints/cli/tests/test_runtime_sign_in_native.py:87-149` does this in four steps:
  - registers the installation with `runtime_installation` (`src/cadrumo/adapters/local_runtime/installation.py:49`)
  - opens `WindowsRuntimeEndpoint` (`src/cadrumo/adapters/local_runtime/windows.py:39`)
  - launches `.venv` `cadrumo-runtime.exe` without `--supervised`, inside a kill-on-close `WindowsProcessScope` (`src/cadrumo/adapters/local_runtime/windows_process.py:189`, `:250`)
  - polls `VerifiedRuntimeConnection` until the runtime is ready

  `src/cadrumo_harness/mcp/tests/test_installed_secret_by_reference.py:78-134` and `src/cadrumo/entrypoints/runtime/tests/test_installed_runtime.py:95-118` are near copies. No shared fixture owns this setup.
- **Through the supervised protocol.** `src/cadrumo/entrypoints/runtime/tests/test_supervised_runtime.py:72-109` speaks the supervisor stream protocol in order to test that protocol. The protocol belongs to the manager (`2026-10-04-runtime-manager-architecture-supervisor-contract-adr`). That contract leaves unsupervised test launches unchanged.
- **Through the manager core.** `dev/runtime_lifecycle/harness.py:49-116` defines `LifecycleHarness`.
  - It takes explicit manager and package paths and a fresh root.
  - It starts the debug manager driver in a test Job and stops it by writing a `manager-stop` file.
  - The driver is built with `fixture-test-mode` (`native/cmake/Manager.cmake:59-68`). Release builds refuse that feature (`native/manager/src/lib.rs:5-6`).
  - `create_profile` (`harness.py:229-249`) creates a profile through the real CLI with a random password it never discloses.
- **The child environment.** `child_environment(STRICT, root)` is defined at `src/cadrumo/core/storage_environment.py:653`.
  - When `received` is omitted, it starts from the ambient environment (`:672-675`).
  - It drops only cleared names and product names (`:682-684`).
  - Every other host variable passes through.

### The CMake `bundle` package

- `just build-native Release bundle` (`justfile:666-669`) builds the `bundle` target (`native/cmake/Packaging.cmake:154-155`, `:235-238`).
- The output is an unzipped, uninstalled tree at `build/windows-x64/stage/Release/app`. On this host it takes 1.3 GB. It contains:
  - `python.exe`, `python.zip` and `cadrumo/site-packages`
  - `cadrumo-manager.exe` and `cadrumo.exe`
  - `bin/aeat.exe`, `bin/cadrumo-mcp.exe` and `bin/cadrumo-runtime.exe`
  - `data/authority`
- `dev/packaging/native/assemble.py:324-351` writes `data/package-manifest.json`.
  - Its `files` map gives a SHA-256 for each of 18 509 files.
  - `inputs.cohort_wheels` gives the hash of the cadrumo wheel.
  - It records no digest of the first-party source.
- Existing code already verifies and runs a copied package:
  - `dev/packaging/native/installation.py:51-57` checks a payload's exact file set and every digest against that manifest.
  - `package_inventory` (`dev/packaging/native/package_inventory.py:74-92`) merges in the delegated documentation inventory.
  - `dev/packaging/native/platforms/windows_verify.py:270-320` copies a package to a verification destination. It runs it with `CADRUMO_LOCAL_STORAGE_ROOT` set to a temporary root and from a hostile working directory.
- The manager launches `P/bin/cadrumo-runtime` with `--storage-root`, `--storage-identity`, `--expected-version` and `--supervised` (`native/manager/src/supervision/launch.rs:138-149`).
  - The runtime gets a cleared, allow-listed environment (`:153-164`).
  - That environment pins the authority to `P/data/authority` (`native/manager/src/supervision/environment.rs:110-140`).
  - `dev/runtime_lifecycle/installed.py:850` sets the same pin for its own probes.
- Other ledgers record the cost. An incremental bundle step took about 472 s and bundle verification about 511 s (ledger line 202 under `.vault/exec/2026-10-07-runtime-file-access-performance/`).
- The staged package on this host is behind the source.
  - Its `build.json` is dated 2026-10-08.
  - It holds 3 284 first-party `.py` files in `cadrumo/site-packages/cadrumo`. Of these, 307 differ by SHA-256 from `src/cadrumo`, and 5 do not exist there.

### Test lanes

- `pyproject.toml:1185` sets `addopts` to select `unit`. It excludes `os_keychain`, `windows_only`, `perf`, `external_tool`, `resident_service` and `private_ingest_corpus`.
- `dev/` is not a default test path (`pyproject.toml:1165-1168`).
- `dev/agent_eval/tests` runs inside three recipes: `test-repository-contracts` (`justfile:1043-1044`), `test-windows` (`:1251`) and `test-os-keychain` (`:1271`). Anything placed under that directory joins those lanes.
- `test-runtime-auth` (`justfile:1275-1276`) is the only recipe for the native sign-in test.
- `src/cadrumo/tests/live_gate.py:19-33` fails an `aeat_live` test unless `CADRUMO_LIVE_TESTS_ENABLED=1`. That gate controls AEAT network access, not model spend.
- No workflow runs on a schedule, and none uses an Anthropic or Claude credential. `merge-gate.yml` is the only pull-request workflow.
- `.logs/` is ignored (`.gitignore:27`) and holds per-run test logs (`dev/test_runs/logging.py:70-81`).

### What the 2026-10-12 demonstration did outside the repository

The demonstration ran from scripts in a throwaway session folder:
- **Host script.** It acted as a stand-in manager.
  - It registered a runtime installation on a fresh root under the session's temporary directory.
  - It built the environment with `child_environment(STRICT)` and pinned `CADRUMO_AUTHORITY_ROOT` to the worktree `.authority`.
  - It wrote that environment to `env.json`.
  - It launched `.venv` `cadrumo-runtime.exe --supervised` and later stopped it by writing the supervisor `stop` frame.
- **Launcher.** It wrote an `mcp.json` pointing at `.venv` `cadrumo-mcp.exe` with that environment. It then ran `claude -p --model claude-haiku-5-5 --output-format stream-json --verbose --strict-mcp-config --mcp-config ... --tools "" --allowedTools mcp__cadrumo --no-session-persistence`. The prompt went in on standard input, and the stream was saved to `transcript.jsonl`.
- **Prompt.** It used a synthetic consultant profile with four third-quarter 2026 ledger rows. The agent first tried a deliberately wrong password. It then created, calculated, verified and exported Modelo 130 and wrote a report. The profile password was substituted into the prompt.
- **CLI wrapper and shell scenario.** These created the profile and read back the ledger, work list and history with `--profile-secrets-stdin`. They parsed the JSON with `grep`.
- **Export check.** It parsed the exported bytes with `parse_export_payload` under `bundled_indexed_authority`.
- **Other scripts.** A transcript summariser, and probes for discovery latency and the keychain.

Results of the two complete runs:
- They took 41 and 44 turns, about 190 s each, and cost about 0.03 to 0.035 USD each.
- Each stream was about 1 MB.
- In both runs, the profile password appeared in the saved transcript.
- Each `mcp.json` carried a Claude Code messaging token, inherited through the ambient environment.

The runs found three defects that the existing test suites had missed:
- A search deadline ended the MCP session.
- Verify and export disagreed on IVA.
- Replies were oversized.

The 2026-07-03 operability measurement (`2026-07-03-agent-harness-operability-followup-audit`) followed the same pattern earlier. A live Opus persona drove the CLI in a sandbox and found a calendar refusal that a seeded scripted test would miss. That run did not keep reproducible tooling either.
