---
tags:
  - '#plan'
  - '#rust-component-provisioning'
date: '2026-10-24'
tier: L2
related:
  - '[[2026-10-24-rust-component-provisioning-adr]]'
  - '[[2026-10-18-dependency-provisioning-unified-setup-adr]]'
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
  - '[[2026-10-17-single-binary-process-tree-adr]]'
modified: '2026-10-24'
body_schema: body-v2
body_hash: 'sha256:9857e3212adc183c798b9397d5e6874f6190510fa53700bd9a2f0178bc675855'
---

# `rust-component-provisioning` plan

One Rust engine downloads, installs, checks and removes the browser and the local AI for every surface. Python only locates and uses them.

## Description

Approved 2026-10-24. Basis: the owner's reply "all approved, implemnet", which also accepted `2026-10-24-rust-component-provisioning-adr` and its amendments to prior rulings.

The work replaces the Python provisioning path that `2026-10-24-rust-component-provisioning-reference` maps. That path is the registered `dependencies.*` operations, Playwright's vendor installer behind a loopback server, and winget or Homebrew plus `/api/pull` for Ollama. In its place comes a provisioning engine in `native/application`, built on the existing `component.rs` store. The engine runs as the single binary's `components` role and is linked in process by the desktop.

Decision coverage, by Phase:

- The proposed Rust ADR governs every Phase. Constraints 1 and 3 to 5 govern P01, constraint 6 governs P02, constraints 7 to 9 govern P03, constraint 2 governs P04, and constraint 12 governs P05. Constraints 10 and 11 govern P01.S02 to P01.S04.
- `2026-10-18-dependency-provisioning-unified-setup-adr` keeps governing the states (D2), the plan-bound approval (D4), the progress vocabulary (D5), retry and recovery (D6), the failure categories (D9), the desktop experience (D10 as amended), the hard requirements (D11) and the storage locations (D12), except where the Rust ADR names a replacement.
- On acceptance, the Rust ADR's listed amendments to the unified-setup, native-bundle, single-binary and desktop-shell records are applied in the same change as the acceptance, before P01 starts.

Interplay with in-flight work:

- `2026-10-24-component-on-demand-plan` lands first. It keeps the item ids and recovery actions this plan preserves.
- `2026-10-18-dependency-provisioning-plan` P08.S27, the packaged setup acceptance, is re-scoped to this plan's P05.S15 lane on acceptance, because the path it would accept is the one deleted here.

New dependencies (tar plus gzip or zstd crates for the Ollama archives on Linux and macOS) are covered by the ADR's hypothesis and go through cargo-deny. Anything that changes an item id, a recovery action or a window contract goes back to the orchestrator.

## Steps

### Phase `P01` - Engine core: pins, transfer, states and plan

The Rust engine gains declarative pins, a proxy-aware pinned transfer with retry and resume, network preflight, item states, the plan digest and a crash-surviving activity record.

- [x] `P01.S01` - Move the browser pins and new local AI pins (program archive per platform; each role's model with manifest digest, size, licence and hardware floor) into declarative package data that Rust and Python both read, and drop the pin copy from the model catalogue; `src/cadrumo/_data/dependencies/, src/cadrumo/core/model_catalogue.py, dev/env/browser_archive_pins.py, a dev/env local AI pin tool, native/cmake/PackageInputs.cmake, native/package-layout.json and tests`.
- [x] `P01.S02` - Give the component store a pinned transfer: CADRUMO_PROXY settings, the HTTPS hop and redirect-host policy, pinned size and SHA-256, transient retry with backoff and jitter, resume of partial bytes, byte progress and cancellation between chunks; `native/application/src/component.rs, native/application/src/provisioning/transfer.rs and Rust tests against local HTTP and TLS servers`.
- [x] `P01.S03` - Add the network preflight with per-item hosts and the offline, unreachable, secure-connection, blocked-by-network and reachable classification; `native/application/src/provisioning/network.rs, native/application-environment.toml and tests`.
- [x] `P01.S04` - Add item declarations, derived states with blocked reasons and failure categories, the plan and its digest, the free-space rule, the per-item writer lock, the activity record with interrupted detection, and receipts; `native/application/src/provisioning/items.rs, state.rs, plan.rs, activity.rs and tests`.

### Phase `P02` - Browser

The engine installs pinned Chromium archives straight into the bundled driver's layout and checks them with its own headless launch; Python only locates the result.

- [x] `P02.S05` - Install each pending pinned Chromium archive into the build directory browsers.json names, write the driver's completion marker set read from its registry code, and remove superseded builds after the new one verifies; `native/application/src/provisioning/browser.rs and tests against a recorded archive`.
- [x] `P02.S06` - Add the browser quick and full checks (marker, executable digest against the receipt, headless launch and version against the pins), the engine's location record, and the item-generic Python reader of component records; `native/application/src/provisioning/browser.rs, browser/launch.rs, receipts.rs, src/cadrumo/core/component_records.py and tests`.
- [x] `P02.S18` - Share one bounded extractor between the component store and the browser, and admit only relative symbolic links that resolve inside the build folder, created after the regular files and verified afterwards, so platform archives that carry them install; `native/application/src/component.rs, native/application/src/provisioning/browser.rs and tests`.

### Phase `P03` - Local AI

The engine installs a pinned portable Ollama, runs it as its own child, pulls and checks each role's model, and decides the hardware floor; Python only locates and uses it.

- [x] `P03.S07` - Install the pinned portable Ollama archive into components/ollama/<version>, start and stop it as the engine's child with the existing models root and home, and detect but never modify a system install; `native/application/src/provisioning/local_ai/program.rs, native/application/Cargo.toml (archive crates through cargo-deny), native/deny.toml and tests`.
- [x] `P03.S08` - Pull each role's model through the started server with byte progress, compare its manifest digest with the pin for stale, run the one-token generation check, and decide the hardware floor from memory and NVIDIA VRAM; `native/application/src/provisioning/local_ai/models.rs, native/application/src/provisioning/local_ai/hardware.rs and tests against a local fake pull server`.
- [x] `P03.S09` - Make the Python readers locate the program, the server's fixed address and the models from the Rust component record, refuse with the local AI setup verdict when no manager runs the server, and move role fitness to consumer admission outside component state; `src/cadrumo/application/local_reader.py, src/cadrumo/application/provisioning_host.py (locate only), src/cadrumo/application/provisioning_fitness.py, src/cadrumo/adapters/outbound/llm/providers/local.py and tests`.
- [x] `P03.S20` - Measure each role's model fitness at its first use as consumer admission, once per installed model digest, and record the verdict, so an unmeasured model is measured before it reads and an unfit one refuses with no setup action; `src/cadrumo/application/local_reader.py, src/cadrumo/application/provisioning_fitness.py, src/cadrumo/adapters/outbound/llm/role_fitness.py, the text-role admission checks in src/cadrumo/entrypoints/ledger_evidence_extraction_composition.py, ledger_llm_composition.py and src/cadrumo/adapters/outbound/llm/statement_reading.py, and tests`.

### Phase `P04` - Role and surfaces

The single binary gains the components role; the desktop calls the engine in process, and the CLI, TUI and MCP become thin clients of the role.

- [x] `P04.S10` - Add the components role to the single binary with its line-delimited JSON protocol for status, plan, setup, verify, cancel and remove, and document it in the package contract; `native/application/src/role.rs, native/application/src/provisioning/protocol.rs, the binary entry, native/CONTRACT.md and tests`.
- [x] `P04.S11` - Point the desktop setup host at the in-process engine and drop its relay of dependencies operations, keeping the window contract unchanged; `native/desktop/src-tauri/src/shell/setup/, native/desktop/src-tauri/src/app.rs and Rust tests`.
- [x] `P04.S12` - Add a Python client that starts the components role and decodes its protocol, and make config provision, config check and the health report thin clients of it with words from the canonical catalogues; `src/cadrumo/adapters/outbound/components/, src/cadrumo/entrypoints/cli/config/provision_cli.py, src/cadrumo/entrypoints/cli/config/check_cli.py, src/cadrumo/application/preflight.py, src/cadrumo/application/diagnostics.py, src/cadrumo/entrypoints/cli/command_operation_table.py and tests`.
- [ ] `P04.S13` - Make the TUI setup screen and the MCP service clients of the same role, with MCP approval bound to the plan digest and progress relayed as notifications; `src/cadrumo/entrypoints/tui/setup/, src/cadrumo_mcp/ and tests`.
- [x] `P04.S17` - Have the runtime manager supervise the engine's local AI server on one fixed Cadrumo loopback address declared in the canonical environment definition: start it while the local AI is set up, restart it after a crash, stop it on exit, at session end and before the engine replaces or removes the program, contain it, and record the address in the local AI component record; `native/manager/src/supervision/, native/application/src/provisioning/local_ai/, native/application-environment.toml, src/cadrumo/core/config_runtime_fields.py (default derived from the declaration) and tests`.
- [x] `P04.S19` - Let the components role adopt browser builds already installed without downloading, then point the Python launch guard at the Rust component record, with test support writing the engine's fixture record into each test storage root; `native/application/src/provisioning/browser.rs, src/cadrumo/application/provisioning_browser.py (locate only), src/cadrumo/adapters/outbound/aeat/browser/session.py, the real-browser test support and conftest, and tests`.
- [x] `P04.S21` - Contain the manager's local AI server on Linux and macOS as the Windows job does, so a crashed or killed manager leaves no server behind; `native/manager/src/supervision/local_ai.rs, native/platform process scope and tests`.
- [ ] `P04.S23` - Let a second setup of an item that is already being set up follow the running one instead of refusing busy, on the role, the desktop host and the Python client, and cover the busy path in tests; `native/application/src/provisioning/engine.rs, protocol.rs, native/desktop/src-tauri/src/shell/setup/components.rs, src/cadrumo/adapters/outbound/components/ and tests`.
- [x] `P04.S24` - Word the licence notice of a pinned role model for what it is and show the licence's display name from the pins instead of its SPDX id; `src/cadrumo/_data/dependencies/local_ai_models.toml, dev/env/local_ai_model_pins.py, native/application/src/provisioning/pins.rs and plan.rs, the desktop.setup licence keys, and tests`.
- [ ] `P04.S25` - Point config provision remove at the components role and retire config provision start, whose server the manager now owns; pass the CADRUMO_PROXY settings to the role from every packaged profile that starts it; find and fix the cause of the intermittent refusing-proxy real-role test; and bring the workstation setup guide in line with the Rust setup; `src/cadrumo/entrypoints/cli/config/provision_cli.py, _provision_command_specs.py, the CLI command policy declarations, native/application-environment.toml, src/cadrumo/adapters/outbound/components/ tests, docs/workstation-setup.md and its translations, and tests`.

### Phase `P05` - Removal and gates

The Python provisioning path is deleted with all its callers, and gates prove no Python provisions anything while every surface reads one engine.

- [ ] `P05.S14` - Delete the dependencies operations, the provisioning actions of local-reader.provision and the Python transfer, network, receipt, installer, archive-server, archive-fetch, package-manager and pull modules with every caller and the contract manifest entries, with no aliases; `src/cadrumo/application/dependency_*.py, src/cadrumo/application/provisioning_*.py, src/cadrumo/application/local_reader_setup_items.py, src/cadrumo/adapters/outbound/browser_runtime/, src/cadrumo/adapters/outbound/model_runtime/process_control.py, src/cadrumo/entrypoints/dependency_operation_composition.py, src/cadrumo/_data/operations/contract_manifest.json and tests`.
- [ ] `P05.S15` - Add the gates: an import and source gate refusing any Python module that downloads, installs or decides component state, Rust fault tests for every transfer failure, four-surface conformance against one engine, and the isolated-root acquisition lane driving the role; `dev/quality/tests/test_no_python_provisioning.py, native/application/tests/provisioning_faults.rs, src/cadrumo/entrypoints/tests/test_components_surface_conformance.py, dev/smoke/acquisition_lane.py`.
- [x] `P05.S16` - Withdraw Python provisioning at once: the product setup composition binds only read-only, withdrawn items whose effect ports refuse, setup refuses not in this build before any plan, review or effect, and local-reader start and remove are refused at access; `src/cadrumo/application/dependency_withdrawal.py, src/cadrumo/application/dependency_setup_operation.py, src/cadrumo/application/local_reader_operation.py, src/cadrumo/entrypoints/dependency_operation_composition.py, src/cadrumo/entrypoints/operation_composition.py and tests`.
- [x] `P05.S22` - Make the local AI record fixture test platform-neutral so its version folder identity does not depend on the platform that generated it, and run the provisioning crate tests on Linux in the gates; `native/application/src/provisioning/local_ai/ tests, src/cadrumo/core/tests/_component_records/local_ai.json and the Rust provisioning gate`.

## Parallelization

Hard ordering:

- P01 lands before P02 and P03. P01.S01 comes first, because every later Step reads the pins.
- P02 and P03 may run in parallel. Their write sets are `provisioning/browser.rs` and `provisioning/local_ai/`, plus the separate Python locate edits.
- P04.S10 needs P01. P04.S11 to P04.S13 need P04.S10 and may run in parallel: the desktop, CLI and TUI-plus-MCP lanes have disjoint write sets.
- P05.S14 runs only after every surface reads the role, so no caller of the deleted code remains.
- P05.S15's gates are authored early and are expected to fail until P05.S14 lands.

Working rules:

- All lanes stay in the shared `tui` worktree. Each Step commits only its own paths through a private index built from HEAD.
- Rust tests run small and serial on the application crate, agreed with any live native build first. rustfmt runs through stdin only.

## Verification

- **Rust.** Fault tests run against real local HTTP and TLS servers: reset, timeout, 5xx, 429, truncation, a wrong digest, an unapproved redirect hop, slow transfer, a full disk, and interruption with resume. Retries stop at the D6 budget, and a transient fault never surfaces as a permanent category. Run them with `cargo test` on `native/application`, plus clippy, rustfmt check and cargo-deny.
- **Browser layout.** A Chromium build installed by the engine launches through the bundled Python Playwright with no vendor installer present. A build without its marker reads absent.
- **Local AI.** A pinned Ollama archive starts as the engine's child. A pull against a local fake registry resumes after interruption. A digest different from the pin reads `stale`. A system Ollama is reported and left untouched.
- **No Python provisions.** The P05.S15 gate fails on a representative fixture: a Python module that spawns an installer, opens a download, or writes a component receipt. `dependencies.setup`, `dependencies.status` and `dependencies.verify` exist nowhere, with no aliases.
- **Parity.** The CLI, TUI, MCP and desktop show the same rows and plan digest from one engine. Approval on any surface performs the same setup. A source checkout without a native build reads `not_in_this_build` everywhere.
- **Quick check.** Bounded at 2 s with no network and no model load, measured through the role.
- **Acceptance.** The isolated-root acquisition lane drives the role in one throwaway root under `build/windows-x64/testing`. It covers setup with approval, forced interruption and Resume without a second review, the full check, a no-op second run, verified cleanup, and unchanged real storage. A vanilla-machine run stays pending until a disposable host exists.
- **Python checks.** `uv run --no-sync lint-imports --config .importlinter --no-cache`, `just check-style`, `just check-format`, `just check-types`, `just check-locales` and `just check-operation-contract-manifest` pass on the touched scope.
- **Review.** Integrated review runs at each Phase close and at plan close, tracing engine, role, client and each surface against both ADRs.
