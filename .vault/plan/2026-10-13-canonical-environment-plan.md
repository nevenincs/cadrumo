---
tags:
  - '#plan'
  - '#canonical-environment'
date: '2026-10-13'
tier: L2
related:
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-10-13-native-agent-adr]]'
  - '[[2026-10-13-package-verification-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
modified: '2026-10-13'
body_schema: body-v2
body_hash: 'sha256:be87c9433605c8f237e4229c7152dd2e4ea731667ae21dec7a6d2382212dd5ab'
---

# `canonical-environment` plan

Make `native/application-environment.toml` the one package-owned declaration from which every interpreter host defines its image's process environment.

## Description

Approved 2026-10-13. Basis: the operator accepted `2026-10-13-canonical-environment-application-internals-adr` on 2026-10-13 and answered "accept. lgtm, proceed" to the stated next action of writing this implementation plan. That is advance authorization for this plan's Steps within the ADR's constraints.

The work adds `native/application-environment.toml` to the CMake project and compiles it in `dev/packaging/native` into `contract.json`, `contract.rs` and `contract.h`. The generator stops importing CLI declarations for the environment contract. `native/platform` and both C hosts define each image's environment from its compiled launch profile and invocation table. A dedicated `bin/cadrumo-agent` image runs the agent gateway and worker. The runtime starts that image and fills only the gateway's declared slots. The CLI narrows its declarations to runs outside a package.

Decision coverage. `2026-10-13-canonical-environment-application-internals-adr` (accepted) governs every Step. Its amendments to the five accepted records are applied. No new costly decision is needed. Mapping of the other governing records:

- `2026-10-04-canonical-environment-adr` and `2026-08-03-canonical-storage-management-adr` R1, as amended: P01 (root rule, vectors and locations move to the file) and P03.S10 (the taxonomy declares only the CLI's own locations).
- `2026-10-03-application-packaging-interpreter-foundation-adr`, as amended: P01 and P02 (native bootstrap defines each image's environment).
- `2026-10-04-runtime-manager-architecture-adr`: P02.S06 (the runtime and its workers stay strict, no operator overrides).
- `2026-10-13-native-agent-adr`, as amended: P02.S07 and P04.S11 (the agent image and the `CADRUMO_PACKAGE_AGENT_SOURCE_DIR` selector).
- `2026-10-13-package-verification-adr`: P03.S09 and P04.S14 unblock its hosted door and proof run. Its plan, `2026-10-13-package-verification-plan`, owns `native/tests/agent_smoke.py` (its S02), `dev/runtime_lifecycle/agent_live.py` (its S03 and S05) and the removal of `native/desktop/src-tauri/src/agent/direct.rs` (its S04). This plan does not edit those files.

Agent-owner items (CADRUMO-AGENT-CODE), as answered from cadrumo-agent `main` at `45edd9f`:

- A1 is resolved in the agent's code. `CADRUMO_AGENT_HOSTED_CLI_EXECUTABLE` and `CADRUMO_AGENT_HOSTED_PYTHON_EXECUTABLE` are retired, and the agent refuses a start that carries either (its `api/app.py` `refuse_terminal_program_settings`). `CADRUMO_AGENT_HOSTED_RELAY_EXECUTABLE` stays. `HOSTING_CONTRACT` stays 1 and `CREDENTIAL_FRAME_VERSION` stays 1. P03.S09 adds the test that neither the composer nor the file emits a retired name. The hosting-contract ADR text amendment belongs to the agent owner and gates no Step here.
- A2 is resolved. `{"version":1,"credentials":{}}` parses. A hosted `serve` then writes `refused hosted_tool_server_unproven`, possibly after `hosted_stores_mismatch` or `hosted_proof_policy` refusals. There is no credential-free ready path by design. P04.S14 asserts that refusal, which proves the gateway received its hosted environment, and accepts `agent_ready` once the agent's proofs are recorded. P04.S14 is not gated.
- A3 is pending on the agent side. Until the non-hosted worker token moves to standard input, P02.S07 admits `CADRUMO_AGENT_INTERNAL_TOKEN` to the agent worker profile only. P04.S16 removes it and is the only Step gated on an agent-owner item (A3).
- A4 is confirmed. Non-frozen `module_command` yields `[sys.executable, "-m", "cadrumo_agent.worker"]`; a truthy `sys.frozen` yields `run-module` instead. P02.S07 therefore requires the image to leave `sys.frozen` unset and to stay `sys.executable`, with a test for both. `cadrumo_agent.worker` is the only module the gateway starts on Windows.

Grounding notes, to be confirmed by the executing Step:

- The gateway module is `cadrumo_agent.cli.main` (`src/cadrumo/adapters/local_runtime/agent_programs.py:32`), so the gateway invocation is `-m cadrumo_agent.cli.main serve`.
- The KDF invocation carries numeric descriptor or handle arguments (`native/interpreter/posix/invocation.h:19-28`, `native/interpreter/windows/host.c:34`). The invocation table therefore needs typed argument positions as well as literals.
- The runtime sends the agent's standard error to the null device today (`src/cadrumo/adapters/local_runtime/windows_process.py:299-307`). P03.S08 must capture it to read the refusal line.
- No recipe or preset sets `CADRUMO_AGENT_SOURCE_DIR` today; P04.S11 updates only the ones it finds.

## Steps

### Phase `P01` - Package declaration and generator

native/application-environment.toml exists, is validated and compiled into contract.json, contract.rs and contract.h, and the generator no longer imports CLI declarations for the environment contract.

- [x] `P01.S01` - Author native/application-environment.toml schema 1 (environment names with kind and validation, per-image launch profiles with base, operator-overridable names, fixed values and pins, PATH policy, pass-through names, launch-parameter slots and invocation tables) and a stdlib-tomllib validator in the generator that refuses schema violations and compiles every profile and invocation table into contract.json, contract.rs and contract.h; declare the file as an input of the contract step beside native/package-layout.json (Contract.cmake:11-13); cover schema validation, malformed-file refusal and file-to-contract.json-to-contract.rs parity; `native/application-environment.toml (new), dev/packaging/native/application_environment.py (new), dev/packaging/native/generate.py, native/cmake/Contract.cmake, dev/packaging/native/tests/test_application_environment.py (new)`.
- [x] `P01.S02` - Move the package facts the generator now reads from the CLI into the file and drop those imports: the storage-root variable, installed default rule per platform and channel and its vectors (storage_vectors.py:8), the package-component locations and desktop defaults (generate.py:342-353; storage_taxonomy.py:224-225 and :291-295 members), the package overrides (package-layout.json:38-41), and the native-host exit range (runtime_exit_reasons.py:8, contracts.py:108-120); remove the Settings, PROCESS_ENVIRONMENT, product_env_var_names and STORAGE_TAXONOMY imports (generate.py:11-27, :127-150, :296-308) and the settings_inputs glob (Contract.cmake:24-26); add a static test that the generator imports no cadrumo module for the environment contract, while product identity and runtime transport stay as non-environment inputs; `dev/packaging/native/generate.py, dev/packaging/native/storage_vectors.py, dev/packaging/native/runtime_exit_reasons.py, native/application-environment.toml, native/package-layout.json, native/cmake/Contract.cmake, dev/packaging/native/tests/test_generator_imports.py (new)`.

### Phase `P02` - Host defines each image's environment

native/platform and both C hosts define every image's process environment from its compiled launch profile and invocation table, the retired allowlists are gone, and the bin/cadrumo-agent image is built.

- [ ] `P02.S03` - Add define_environment(profile, ambient) to native/platform: start from the declared base, pass declared operator and pass-through names, resolve and pin the root by the package rule, set fixed values, admit declared slots after kind validation (existing absolute directory, port 0..65535, existing non-batch file, descriptor number), and set PATH composed from the layout's binary directories plus the packaged Python distribution's binary and scripts directories and CADRUMO_EXTERNAL_BIN_DIRS as its existing override allows; replace cleared, pinned, executable_search_path and the prepare filter (lib.rs:138-210) and expose it through the C ABI; `native/platform/src/lib.rs, native/platform/src/storage.rs, native/platform/tests/consumer.c`.
- [ ] `P02.S04` - Emit per-profile environment vectors from the file (ambient in, defined environment or refusal out, including generic python clearing the CADRUMO_AGENT_ prefix, the kdf-child pass-through, agent gateway and worker admission and undeclared-invocation refusal) and replay them in Rust and in Python; `dev/packaging/native/application_environment.py, native/platform/src/conformance_tests.rs, native/platform/src/posix_tests.rs, dev/packaging/native/tests/test_launch_profile_vectors.py (new)`.
- [ ] `P02.S05` - Replace the hand-written supervised_kdf_invocation (windows/host.c:34, :136; posix/invocation.h:19; posix/host.c:108) with matching of argv against the generated invocation table before Python starts, apply the kdf-child profile (parent-defined environment unchanged, isolated paths and package verification kept), and on a launch-profile violation exit 125 after writing one last stderr line {native_refusal, subject} with code launch_value_missing, launch_value_malformed or invocation_undeclared and never the value; `native/interpreter/windows/host.c, native/interpreter/posix/host.c, native/interpreter/posix/invocation.h, native/interpreter/posix/tests/invocation.c, native/platform/src/lib.rs`.
- [ ] `P02.S06` - Retire RESERVED_ENV, PACKAGE_ENV_ALLOWLIST, the product-allowlist filter and layout overrides with every consumer in one change: move the manager's runtime launch (supervision/environment.rs:131, launch.rs:193-202) and the desktop projection (desktop environment.rs:348) onto define_environment, update startup_logging.rs and terminal/tests/live.rs, drop the generator emissions (generate.py:379-381) and the old contract tests; `native/platform/src/storage.rs, native/platform/src/lib.rs, native/manager/src/supervision/environment.rs, native/manager/src/supervision/launch.rs, native/manager/tests/environment.rs, native/manager/tests/supervision.rs, native/desktop/src-tauri/src/environment.rs, native/desktop/src-tauri/src/startup_logging.rs, native/desktop/src-tauri/src/terminal/tests/live.rs, dev/packaging/native/generate.py, dev/packaging/tests/test_native_storage_environment_contract.py`.
- [ ] `P02.S07` - Build the compiled bin/cadrumo-agent image from the same C host: widen the layout rule (layout.py:66-69) to package-declared images for a bundled distribution, declare the image in package-layout.json and its CMake targets, keep the image as sys.executable and leave sys.frozen unset (unlike host.c:63-75), admit only the gateway invocation (-m cadrumo_agent.cli.main serve) and the worker invocation (-m cadrumo_agent.worker), declare the gateway slots (hosted root, ports, relay) and gateway names including CADRUMO_AGENT_DEVELOPMENT_TOOL_SERVER and CADRUMO_AGENT_PROVIDER_PROOF_POLICY, never CADRUMO_AGENT_ENV_FILE, and admit CADRUMO_AGENT_INTERNAL_TOKEN to the worker profile only; test that sys.frozen is unset and sys.executable is the image; `dev/packaging/native/layout.py, native/package-layout.json, native/application-environment.toml, native/interpreter/windows/host.c, native/interpreter/posix/host.c, native/cmake/platforms/Windows.cmake, native/cmake/platforms/Posix.cmake, native/cmake/LaunchGuard.cmake, native/cmake/Packaging.cmake, dev/packaging/native/tests/test_agent_image.py (new)`.

### Phase `P03` - Runtime and CLI consume

The runtime starts the agent image, fills only the gateway's declared slots, maps a native refusal to agent_service_failed, and the CLI stops being the source of package environment facts.

- [x] `P03.S08` - Widen the native_host reserved range to 120-125 with 125 meaning launch_profile_refused (contracts.py:108-120); capture the agent's standard error instead of the null device (windows_process.py:299-307, agent_process.py:121-140) and, when the gateway or worker exits 125 before its ready line, end the launch with agent_service_failed through launcher_refusal_for (launcher_protocol.py:65; controller.py:252-287) and record the native code and subject in redacted diagnostics; the desktop's closed refusal set is unchanged; `src/cadrumo/application/runtime/contracts.py, src/cadrumo/adapters/local_runtime/windows_process.py, src/cadrumo/adapters/local_runtime/agent_process.py, src/cadrumo/application/agent_host/controller.py, src/cadrumo/application/agent_host/launcher_protocol.py, their tests`.
- [ ] `P03.S09` - Rework the agent launch: start bin/cadrumo-agent at the path the runtime image's profile fixes instead of sys.executable -m cadrumo_agent serve (agent_programs.py:55-101), stop reading the package manifest (agent_programs.py:73-87 and its runtime_package_directory use), fill only the gateway's declared slots (launch_environment.py:86-119), retire FORBIDDEN_PROGRAM_STEMS, agent_search_path and the confinement docstring (launch_environment.py:1-13, :48-55, :111-112, :122-143) with their tests, and add a test that neither the composer nor the file ever emits the retired hosted CLI and Python executable names, which the agent now refuses; `src/cadrumo/application/agent_host/launch_environment.py, src/cadrumo/adapters/local_runtime/agent_programs.py, src/cadrumo/entrypoints/runtime/profile_connection_agents.py, src/cadrumo/application/agent_host/tests/test_launch_environment.py, src/cadrumo/entrypoints/runtime/tests/test_agent_host_runtime.py`.
- [ ] `P03.S10` - Narrow the CLI's environment declarations to runs outside a package: retire PROCESS_ENVIRONMENT's host classes and authority pin (storage_environment.py:249-258) and the allowlist role of product_env_var_names (:620) and Settings.storage_env_var_names (config.py:991-1000), remove the desktop, console and manager taxonomy members the file now declares (storage_taxonomy.py:224-225, :291-295) after confirming no CLI consumer, and reduce the worker launch literals (worker_environment.py:14, profile_worker.py:274) to the slots their profiles declare, keeping the CLI's own built-in default root; `src/cadrumo/core/storage_environment.py, src/cadrumo/core/config.py, src/cadrumo/core/storage_taxonomy.py, src/cadrumo/core/storage_taxonomy_locations.py, src/cadrumo/adapters/local_runtime/worker_environment.py, src/cadrumo/adapters/local_runtime/profile_worker.py, dev/packaging/native/package_launch_smoke.py, their tests`.

### Phase `P04` - Guards, conformance probes and documentation

Renames, the CADRUMO_AGENT_ spelling guard, the package-side drift and data-folder checks, the CTest launch probe and the documentation hold the new contract in place.

- [x] `P04.S11` - Rename the CMake selector CADRUMO_AGENT_SOURCE_DIR to the cache-only CADRUMO_PACKAGE_AGENT_SOURCE_DIR and remove its environment fallback (Agent.cmake:2-9), update CONTRACT.md:524 and the build recipes and presets that set it, and rename the remaining Cadrumo-defined CADRUMO_AGENT_ developer names (CADRUMO_AGENT_CHECKOUT at justfile:532-541 and its consumers, CADRUMO_AGENT_LIVE_* in the desktop live tests) to names outside the agent prefix; `native/cmake/Agent.cmake, native/CONTRACT.md, justfile, CMakePresets.json, dev/provider_catalog/generate.py, dev/provider_catalog/tests/test_generate.py, native/desktop/frontend/scripts/agent-catalog-fixture.mjs, native/desktop/frontend/tests/live/`.
- [ ] `P04.S12` - Add the structural gate that refuses any CADRUMO_AGENT_ spelling in src, native, dev, CMake and the justfile outside native/application-environment.toml, the runtime's launch composer, the generated contract and the gate's own fixture data (including the S09 retired-name refusal fixture), with planted-defect fixtures per language proving it detects a spelling; runs after S11 and after package-verification S03 and S04 remove agent_live.py's checkout names and direct.rs; `dev/quality/tests/test_agent_prefix_spelling.py (new) and its fixtures`.
- [ ] `P04.S13` - Add the package-side conformance check run against the assembled package: the names and kinds each image sets, passes or lets operators override agree with the installed CLI's published environment reference and the bundled agent's setting_env declarations; the runtime composer writes exactly the gateway slots; the runtime's reserved native-host range equals the file's; and the CLI's built-in default root equals the package's declared root for each platform and channel; register it in CTest; `dev/packaging/native/environment_conformance.py (new), dev/packaging/native/tests/test_environment_conformance.py (new), native/cmake/Packaging.cmake`.
- [ ] `P04.S14` - Add the CTest launch probe on the assembled package: through the runtime's real composer and the real host the bundled gateway and its worker receive their declared environment, cadrumo-agent stores-state answers for a synthetic hosted root, a hosted serve given the frame {version 1, empty credentials} writes refused hosted_tool_server_unproven (and is written to accept agent_ready once the agent's proofs exist), the generic python image clears every CADRUMO_AGENT_ name, each image's PATH equals the declared composition, and the default root agrees; agent names are read from contract.json, not spelled; `native/tests/environment_launch_probe.py (new), native/cmake/Packaging.cmake`.
- [ ] `P04.S15` - Update the documentation: native/CONTRACT.md source ownership, bootstrap, application images, mutable data and desktop launch projection sections for the file, launch profiles, the agent image, exit 125 and the renamed selector; and regenerate the environment reference so it states which names a packaged image passes; `native/CONTRACT.md, dev/docs/env_reference.py, docs/reference/environment-overrides.md`.
- [ ] `P04.S16` - Remove CADRUMO_AGENT_INTERNAL_TOKEN from the agent worker profile and its vectors once cadrumo-agent moves the non-hosted worker IPC token to standard input (gated on agent-owner item A3); `native/application-environment.toml, native/platform/src/conformance_tests.rs, dev/packaging/native/tests/test_launch_profile_vectors.py`.

## Parallelization

Hard ordering:

- P01.S01 precedes every other Step. P01.S02 follows it.
- P02.S03 follows P01. P02.S04, P02.S05 and P02.S06 follow P02.S03. P02.S07 follows P02.S05, because the agent image uses the invocation table.
- P03.S08 can start at once: it touches only Python runtime files. Its exit-range change reaches the contract when P01.S02 moves that range into the file.
- P03.S09 follows P02.S07, because it starts the agent image.
- P03.S10 follows P01.S02 and P02.S06, because the generator and the native consumers must stop reading the CLI declarations first.
- P04.S11 can run alongside P02 and P03. P04.S12 follows P04.S11, P03.S09 and package-verification S03 and S04.
- P04.S13 and P04.S14 follow P03.S09 and P03.S10 and need an assembled package.
- P04.S15 runs last. P04.S16 waits on agent-owner item A3 and on P02.S07.

Parallel assignments, with disjoint write ownership:

- Native lane: P01.S01, P01.S02, P02.S03 to P02.S07, then P04.S16. Owns `native/application-environment.toml`, `dev/packaging/native/generate.py`, `application_environment.py`, `storage_vectors.py`, `runtime_exit_reasons.py`, `layout.py`, `native/package-layout.json`, `native/platform`, `native/interpreter`, `native/manager`, `native/desktop/src-tauri/src/environment.rs`, `startup_logging.rs`, and `native/cmake` except `Agent.cmake`.
- Runtime lane: P03.S08, then P03.S09, then P03.S10. Owns `src/cadrumo/application/runtime`, `src/cadrumo/application/agent_host`, `src/cadrumo/adapters/local_runtime`, `src/cadrumo/entrypoints/runtime`, `src/cadrumo/core/storage_environment.py`, `config.py`, `storage_taxonomy.py`, `storage_taxonomy_locations.py`, and `dev/packaging/native/package_launch_smoke.py`.
- Rename lane: P04.S11, then P04.S12. Owns `native/cmake/Agent.cmake`, `justfile`, `CMakePresets.json`, `dev/provider_catalog`, `native/desktop/frontend`, and `dev/quality/tests/test_agent_prefix_spelling.py`. Its edit to line 524 of `native/CONTRACT.md` goes in before P04.S15.
- Package-check lane: P04.S13 and P04.S14 together, after the native and runtime lanes. Owns `dev/packaging/native/environment_conformance.py`, `native/tests/environment_launch_probe.py`, and the new test registrations in `native/cmake/Packaging.cmake`. The native lane must have finished its own `Packaging.cmake` edit from P02.S07 first.
- Documentation: P04.S15, single writer of `native/CONTRACT.md` and `dev/docs/env_reference.py`.

Shared hot spots. `native/cmake`, `native/platform` and `dev/packaging/native/generate.py` serialize within the native lane. A worker outside that lane does not edit them. Contract changes regenerate `contract.rs`, which the platform crate, manager and desktop all compile. Rebuild and run their tests before any commit that touches the generator.

Worktree constraints:

- `build/windows-x64` has a single owner at a time. Any other lane uses its own build directory and does not configure, build or clean that one.
- Other sessions have uncommitted edits in this worktree: registry exports under `src/cadrumo/_data/registry`, `dev/tui` and `dev/registry`. Do not stage, revert, stash or format those paths. Stage only the paths of the Step being committed.
- DEV-RUNNER2 is republishing the registry until about 23:30 on 2026-10-13. Until it finishes, do not start a full `just test-native-bundle` or any build that consumes `registry_authority`. Focused generator, Rust and Python tests may run.

## Verification

Each Step closes on its own focused checks. The plan is complete when every Step is closed and the integrated review at each Phase close and at plan close passes.

Focused checks:

- Generator and package Python: `uv run --no-sync pytest dev/packaging/native/tests/test_application_environment.py dev/packaging/native/tests/test_generator_imports.py dev/packaging/native/tests/test_launch_profile_vectors.py dev/packaging/native/tests/test_agent_image.py dev/packaging/native/tests/test_environment_conformance.py dev/packaging/tests/test_native_storage_environment_contract.py`. Malformed-file fixtures must fail generation.
- Rust: `cargo test` for `native/platform`, `native/manager` and `native/desktop/src-tauri`. The platform crate replays every launch-profile vector, including undeclared-invocation refusal.
- C host: the POSIX invocation test `native/interpreter/posix/tests/invocation.c` and the platform consumer test `native/platform/tests/consumer.c`, through their CTest registrations.
- Runtime: `uv run --no-sync pytest src/cadrumo/application/agent_host/tests src/cadrumo/application/runtime/tests src/cadrumo/adapters/local_runtime/tests/test_agent_process_native.py src/cadrumo/entrypoints/runtime/tests/test_agent_host_runtime.py src/cadrumo/core/tests`. An exit 125 before the ready line must map to `agent_service_failed`, and a retired hosted-program name must never be emitted.
- Guards: `uv run --no-sync pytest dev/quality/tests/test_agent_prefix_spelling.py dev/quality/tests/test_no_git_cli.py`. The spelling gate's planted fixtures must fail.
- Docs: `uv run --no-sync pytest dev/docs/tests/test_env_reference.py`, after regenerating with `uv run --no-sync python -m dev.docs.env_reference`.

Repository gates, on the touched scope: `just check-import-boundaries`, `just check-style`, `just check-format` and `just check-types`. Do not narrow their configured scopes.

Package gate: `just test-native-bundle Debug`, with CTest running `bundle.agent`, `bundle.python`, the entrypoint tests, the P04.S13 conformance test and the P04.S14 launch probe. The probe must show:

- the gateway and the worker received their declared environment;
- `stores-state` answered for a synthetic hosted root;
- a hosted `serve` with an empty frame wrote `refused hosted_tool_server_unproven`, or `agent_ready` once the agent's proofs exist;
- the generic `python` image cleared every `CADRUMO_AGENT_` name;
- each image's `PATH` equals the declared composition;
- the CLI's default root equals the package's declared root.

Report new regressions separately from evidenced pre-existing failures.
