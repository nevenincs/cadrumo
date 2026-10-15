---
tags:
  - '#exec'
  - '#startup-service-repair'
date: '2026-10-14'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:5b62e4080b9f4c494e0e837d33ff48c509c88112f4ce260e52dbe4b65008cc35'
related:
  - "[[2026-10-14-startup-service-repair-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `startup-service-repair` ledger

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

- `S04` `M` `src/cadrumo/adapters/local_runtime/profile_worker_transport.py`
- `S04` `M` `src/cadrumo/adapters/local_runtime/server_connection_handling.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_worker_supervision.py`
- `S04` `verify:` `focused transport and server tests (50)` -> `pass`
- `S04` `verify:` `focused KDF diagnostics cleanup exit tests (34)` -> `pass`
- `S01` `M` `src/cadrumo/adapters/local_runtime/agent_diagnostics.py`
- `S01` `M` `src/cadrumo/application/agent_host/store_lifecycle.py`
- `S01` `M` `src/cadrumo/core/diagnostic_log.py`
- `S01` `M` `native/application/src/diagnostics/service.rs`
- `S01` `M` `native/desktop/frontend/src/components/records/RecordRow.tsx`
- `S01` `M` `native/desktop/frontend/src/components/AgentColumn.tsx`
- `S01` `verify:` `focused Python diagnostics lifecycle environment tests (83 original; new lifecycle regression passed in 138-test run)` -> `pass`
- `S01` `verify:` `diagnostic privacy and containment tests (34)` -> `pass`
- `S01` `verify:` `npm run check` -> `pass`
- `S01` `verify:` `Playwright agent refusal and explicit retry scenario` -> `pass`
- `S02` `M` `native/desktop/src-tauri/src/agent/supervisor.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S02` `A` `native/desktop/src-tauri/src/shell/sign_in/reads.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/sign_in/process.rs`
- `S02` `M` `native/application/src/diagnostics/helper.rs`
- `S02` `verify:` `Rust sign_in focused tests (52 before helper outcome correction)` -> `pass`
- `S02` `verify:` `Rust agent supervisor tests (9 before review correction)` -> `pass`
- `S02` `verify:` `run-backend Unit Filter agent::supervisor final 10 tests` -> `pass`
- `S02` `verify:` `run-backend Unit Filter nonzero_exit_is_reported real helper regression` -> `pass`
- `S02` `verify:` `npm run check after helper outcome contract update` -> `pass`
- `S03` `verify:` `bundle.image from GUI verification session` -> `pass`
- `S03` `verify:` `bundle.environment-launch from GUI verification session` -> `fail`
- `S03` `verify:` `just check-code` -> `fail`
- `S03` `verify:` `just test-gate collection (run stopped after confirmed unrelated failure)` -> `fail`
- `S03` `verify:` `cmake app-agent incremental wheel update46 files (no dependencies or native rebuild)` -> `pass`
- `S03` `verify:` `ctest bundle.environment-launch20.42s after incremental agent update` -> `pass`
- `S01` `M` `src/cadrumo_agent_service/main.py`
- `S01` `M` `src/cadrumo_agent_service/service.py`
- `S01` `A` `src/cadrumo_agent_service/host/tests/test_service_failure.py`
- `S01` `verify:` `service unit suite 243 tests` -> `pass`
- `S01` `verify:` `service Windows integration suite 23 tests` -> `pass`
- `S01` `verify:` `manual packaged service admission and protected credential CAS set/remove/reset` -> `pass`
- `S02` `verify:` `native desktop Release compilation` -> `pass`
- `S03` `M` `dev/runtime_lifecycle/agent_live.py`
- `S03` `verify:` `live person driver and holder 20 unit tests` -> `pass`
- `S03` `verify:` `just check-registry-gate` -> `pass`
- `S05` `M` `native/application-environment.toml`
- `S05` `M` `native/platform/src/launch.rs`
- `S05` `M` `src/cadrumo_agent_service/host/launch_environment.py`
- `S05` `M` `src/cadrumo_agent_service/host/tests/test_launch_environment.py`
- `S05` `M` `dev/packaging/native/environment_conformance.py`
- `S05` `M` `dev/packaging/native/tests/test_environment_conformance.py`
- `S05` `verify:` `ctest platform.resolver including external directory gateway and worker regression` -> `pass`
- `S05` `verify:` `environment conformance and composer focused tests` -> `pass`
- `S05` `verify:` `focused Ruff rustfmt and ty` -> `pass`
- `S03` `verify:` `selected Codex user home login status exit0 and hosted profile home exit1` -> `pass`
- `S05` `M` `native/CONTRACT.md`
- `S05` `verify:` `native contract search-path paragraph reconciled with declared gateway and worker pass-through` -> `pass`
- `S05` `verify:` `final service unit and Windows integration suite 268 tests` -> `pass`
- `S05` `verify:` `environment conformance 59 tests` -> `pass`
- `S05` `verify:` `current Import Linter 24 contracts` -> `pass`
- `S03` `verify:` `cmake --build build/windows-x64 --config Release --target app-payload` -> `pass`
- `S03` `verify:` `staged python native/tests/environment_launch_probe.py after external-directory repair` -> `pass`
- `S03` `verify:` `temporary live package proof agent-live-5hu58oe3` -> `fail`
- `S03` `verify:` `fresh manual packaged service admin agent-manual-ob5uo5er` -> `pass`
- `S03` `verify:` `fresh manual packaged runtime shutdown agent-manual-ob5uo5er` -> `fail`
- `S03` `verify:` `pytest agent_live and session_holder unit tests (24)` -> `pass`
- `S03` `verify:` `live package proof agent-live-l2a5ehrv` -> `fail`

## Notes

- `S04` Initial 10s worker stall and 30s cleanup cause remain unproven; typed request/action and cleanup subspan diagnostics support next reproduction.
- `S01` Broader code checks and final packaged verification pending. Unrelated concurrent changes preserved.
- `S02` Review correction preserves exhausted retries through failed status observations. New nonzero helper exit outcome regression and final native build pending.
- `S03` Original uppercase agent loglevel corrected: packaged stores-state/setup/current pass. Gateway/worker blocked by missing `lane_effort_control` import in bundled agent; GUI session owns incremental artifact investigation via build/message.txt. No dependency changes. User requires affected-artifact incremental builds only.
- `S03` Resolved stale mixed staged agent selection/effort import using existing app-agent target. Full real GUI sign-in verification handed to coordinating session through build/message.txt; historical KDF cleanup and worker stall remain evidence questions.
- `S01` Hosted gateway still refuses `hosted_lane_unproven;` provider CLI auth is absent from its hosted provider home.
- `S05` Refreshed package and live model turn pending. No hosted CLI credential provisioning was added.
- `S03` User 2026-10-15 explicitly requires separate provider sign-in in each Cadrumo profile CLI home; do not import external account credentials. Current `provider_sign_in` setting records a mode but performs no login.
- `S03` Fresh Release payload completed. Installed service.py and `launch_environment.py` text match source; byte hashes differ only due to newline normalization. Launch probe passes stores, standalone worker and environment sanitation while hosted gateway still truthfully refuses `hosted_lane_unproven.` Live proof retry ended before agent launch: runtime did not emit readiness within the existing deadline. No model turn or hosted authentication claimed.
- `S03` Real runtime, password-held CLI person, service admission, twelve-provider catalog/status, protected synthetic credential CAS set/remove/reset and asynchronous start acknowledgement completed. Both starts log `hosted_lane_unproven.` Despite temporary coordinator exit0, runtime stderr records ProfileWorkerRetireRequest timeout10s and native containment guard deadline; shutdown is failed evidence and is under investigation.
- `S03` External search-directory repair is now observed in the unmodified staged gateway: codex/cli selectable, gpt-6.1-sol admitted, packaged worker receives dispatch. Turn fails before a model response because the manual driver seats the isolated Codex runtime beneath the Git repository; provider refuses it. Tool relay also exceeds its30s start/list deadline. Driver now uses system temp outside repositories, preserving the guard; retry underway.
