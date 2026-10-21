---
tags:
  - '#plan'
  - '#dependency-provisioning'
date: '2026-10-18'
tier: L2
related:
  - '[[2026-10-18-dependency-provisioning-unified-setup-adr]]'
  - '[[2026-06-15-dependency-provisioning-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-10-04-google-app-identity-adr]]'
  - '[[2026-10-11-mcp-parity-full-parity-adr]]'
modified: '2026-10-18'
body_schema: body-v2
body_hash: 'sha256:00a199472c938f8036d9a2a8f8c5f8668b1a005b0eb1e83426f046bb3b748796'
---

# `dependency-provisioning` plan

One setup system for the local model, the browser and Google, from registry to every front end.

## Description

Approved 2026-10-18. Basis: the owner's advance authorization, relayed by the coordinating session: "Good, I forgo approval, all yours to deliver. How cool and exciting we're implementing this!" It covers this plan and the accepted `2026-10-18-dependency-provisioning-unified-setup-adr`.

The work builds the unified setup system that ADR decides: one dependency registry with derived states; downloads and installs under the registered `dependencies.setup` operation, with plan-bound approval, subject progress, retry, resume and independent verification; plain wording; and parity across CLI, TUI, MCP and desktop. Grounding: `2026-10-18-dependency-provisioning-mechanisms-reference`.

Decision coverage, by Phase:

- The unified-setup ADR governs every Phase. D1 to D7 govern P01 to P04, D8 governs P07, D9 governs P01.S05 and every surface, and D10 and D11 govern P05 and P06.
- `2026-06-15-dependency-provisioning-adr` (probe contract, amended 2026-10-18) governs P01.S06 and every probe.
- `2026-10-04-desktop-shell-adr` and `2026-10-05-desktop-design-system-adr` (both amended 2026-10-18) govern P05 and P06.
- `2026-10-04-google-app-identity-adr` (amended 2026-10-18) governs P04.
- `2026-10-11-mcp-parity-full-parity-adr` governs P07: no MCP refusal beyond the Google sign-in authentication act.

No other costly decision is open. Anything that would change an operation id or schema beyond the ADR, add a dependency, or touch filing is a new decision and goes back to the orchestrator.

## Steps

### Phase `P01` - Mechanism: registry, operations, transfer and wording

Lane A delivers the dependency registry, derived states, the status, setup and verify operations with plan-bound review and subject progress, network preflight, retry and resume, receipts, and the shared plain wording that every other lane builds on.

- [x] `P01.S01` - Publish the dependency registry contracts: item declaration, states with blocked reasons, failure categories, setup plan and plan digest, and the optional progress subject; `src/cadrumo/application/dependency_registry.py, src/cadrumo/application/dependency_contracts.py, src/cadrumo/application/operations/persistence/events.py, src/cadrumo/application/operations/frontend_requests.py and their tests`.
- [x] `P01.S02` - Add network preflight with per-item host declarations, outcome classification and proxy settings for Cadrumo-started traffic; `src/cadrumo/application/dependency_network.py, src/cadrumo/core/external_constants.toml and tests against a local TLS server`.
- [x] `P01.S03` - Add transfer retry with backoff and jitter, the free-space check, the per-item lock and the receipt store with its new storage category; `src/cadrumo/application/dependency_transfer.py, src/cadrumo/application/dependency_receipts.py, src/cadrumo/core/storage_taxonomy.py, src/cadrumo/core/storage_taxonomy_locations.py and tests`.
- [x] `P01.S04` - Register dependencies.status, dependencies.setup and dependencies.verify with plan review, throttled progress, cancellation and idempotent submit, and remove the browser-runtime registration; `src/cadrumo/application/dependency_setup_operation.py, src/cadrumo/entrypoints/dependency_operation_composition.py, src/cadrumo/entrypoints/local_reader_operation_composition.py, src/cadrumo/entrypoints/operation_composition.py, src/cadrumo/application/operations/access_facts.py and tests`.
- [x] `P01.S05` - Author the plain wording for states, actions and failure categories in four languages, with the typed mapping and the redacted copy-details report; `src/cadrumo/application/dependency_wording.py, the provisioning subtree of src/cadrumo/locales/*/application.yml through the dev.locales workflow, and tests`.
- [x] `P01.S06` - Feed config check and the health report from the registry rows; `src/cadrumo/application/preflight.py, src/cadrumo/application/diagnostics.py and tests`.

### Phase `P02` - Local model: runtime program and per-role models

Lane B turns the model runtime and each catalogue role into registry items with planned install, resumable pull with byte progress, digest pins, quick and full checks, and trims local-reader.provision to actions that download nothing.

- [x] `P02.S07` - Implement the model_runtime and local_model items: plan sizes, install through the plan review, pull with subject progress and transient-failure classification, cancellation that keeps partial blobs; `src/cadrumo/application/provisioning_runtime.py, src/cadrumo/application/provisioning_host.py, src/cadrumo/application/local_reader_provisioning.py, src/cadrumo/adapters/outbound/model_runtime/, src/cadrumo_runtime/adapters/worker_authorization.py, src/cadrumo_runtime/adapters/worker_authorization_lease.py, src/cadrumo_runtime/host/operation_authority.py and tests`.
- [x] `P02.S08` - Pin an expected digest per catalogue model, apply the stale-or-failed rule through the fitness probe, align the readiness probe's keep-alive and name, and provide the quick and full checks; `src/cadrumo/core/model_catalogue.py, src/cadrumo/application/provisioning_fitness.py, src/cadrumo/application/provisioning_runtime.py, src/cadrumo/application/local_reader.py and tests`.
- [x] `P02.S09` - Remove the install, pull and setup actions and the consent field from local-reader.provision and move every caller; `src/cadrumo/application/local_reader_contracts.py, src/cadrumo/application/local_reader_operation.py, src/cadrumo/application/local_reader_provisioning.py, src/cadrumo/application/local_reader_setup_items.py, src/cadrumo/application/provisioning*.py, src/cadrumo/application/dependency_contracts.py (plan entry advisories), src/cadrumo/application/dependency_setup_operation.py (review licence notice), src/cadrumo/entrypoints/local_reader_operation_composition.py, src/cadrumo/_data/operations/contract_manifest.json, src/cadrumo/application/tests/local_reader_operation_requests.py, src/cadrumo/adapters/persistence/operations/tests/local_reader_operation_support.py, src/cadrumo/entrypoints/tests/registered_executor_*.py and tests`.

### Phase `P03` - Browser: Chromium builds

Lane C turns the Playwright Chromium builds into a registry item with byte progress, proxy, partial-build recovery, cancellation, an independent launch check, receipts and cleanup of superseded revisions.

- [x] `P03.S10` - Read the installer's output in bounded form for byte progress, pass proxy settings, delete partial builds before retry, and stop the installer tree on cancel; `src/cadrumo/application/provisioning_browser.py, src/cadrumo/adapters/outbound/browser_runtime/installer.py and tests`.
- [x] `P03.S11` - Add the full check (headless launch and version against browsers.json), the receipt digest manifest, superseded-revision cleanup, and delete the browser-runtime operation module; `src/cadrumo/application/provisioning_browser.py, src/cadrumo/application/browser_runtime_operation.py and tests`.

### Phase `P04` - Google: sign-in readiness

Lane D makes Google a registry item whose status checks the token and its client binding, whose full check refreshes and reads the root folder, whose failures map to the closed categories, and whose sign-in can start from a verified person connection.

- [x] `P04.S12` - Check token presence and client binding in status, add the full check with refresh and root-folder metadata read, and replace substring error classification with typed categories; `src/cadrumo/adapters/outbound/google/sign_in_state.py, src/cadrumo/adapters/outbound/google/oauth_flow.py, src/cadrumo/entrypoints/google_configuration_operation_composition.py and tests`.
- [x] `P04.S13` - Admit a kernel-verified person connection at the interactive gate, make the granted-scope check one rule, and expose sign-in for the desktop and TUI hand-off; `src/cadrumo/adapters/outbound/google/oauth_flow.py, src/cadrumo_runtime/commands/google.py, src/cadrumo_runtime/commands/google_auth_specs.py, src/cadrumo_client/commands/google_consent_admission.py, src/cadrumo_client/commands/google_consent_exchange.py, src/cadrumo_client/commands/google_consent_observation.py, src/cadrumo_client/commands/google_configuration_receipt_correlation.py and tests, including src/cadrumo_runtime/commands/tests/config/test_runtime_google_consent.py`.

### Phase `P05` - Desktop host and person bridge

Lane E publishes the setup host contract, adds the closed setup and Google sign-in actions to the held person bridge with the setup change cue, and implements the token-checked host commands and snapshot channel.

- [x] `P05.S14` - Publish the setup contract types and the optional setup methods of the Host port; `native/desktop/frontend/src/ipc/contract.ts, native/desktop/frontend/src/shell/host.ts, native/desktop/frontend/src/shell/tauriHost.ts`.
- [x] `P05.S15` - Add the closed setup status, start, review answer, cancel, observe and Google sign-in actions to the session hold, and forward the operation change cue for observed setup operations; `src/cadrumo_runtime/host/session_hold.py and tests`.
- [x] `P05.S16` - Implement the host setup commands, the pushed setup event and the typed snapshot channel; `native/desktop/src-tauri/src/shell/setup/, native/desktop/src-tauri/src/agent/person.rs, native/desktop/src-tauri/src/app.rs and Rust tests`.

### Phase `P06` - Desktop frontend

Lane F builds the Components section, the setup dialog, progress, prompts, rail badge, toasts and palette actions on the published Host port, with scenario coverage and desktop strings.

- [x] `P06.S17` - Build the Components section and the setup dialog with plan, approval, per-item progress, retry notices, error sentence with action, copy details and cancel; `native/desktop/frontend/src/components/setup/, native/desktop/frontend/src/components/Settings.tsx`.
- [x] `P06.S18` - Add the first-run and blocked-feature prompts, the Settings rail badge, completion toasts and the setup palette actions; `native/desktop/frontend/src/App.tsx, native/desktop/frontend/src/components/Rail.tsx`.
- [x] `P06.S19` - Add setup scenarios to the development scenario host, stories, and the desktop setup strings in four languages; `native/desktop/frontend/src/shell/ scenario host modules, native/desktop/frontend/src/components/setup/*.stories.tsx, dev/locales/desktop_chrome.py, the desktop.setup subtree of src/cadrumo/locales/*/common.yml`.

### Phase `P07` - CLI, TUI and MCP parity

Lane G routes every config provision verb through the registered operations, adds the operator actions, gives the TUI a setup screen, and relays setup progress and review on MCP.

- [x] `P07.S20` - Route every config provision verb through the runtime operations with plan printing, the yes flag, one progress line and plain errors, and map them in the command table; `src/cadrumo/entrypoints/cli/config/provision_cli.py, src/cadrumo/entrypoints/cli/config/_provision_command_specs.py, src/cadrumo/entrypoints/cli/command_operation_table.py, the provision subtree of src/cadrumo/locales/*/cli.yml, the principal-approved src/cadrumo/entrypoints/cli/config/check_cli.py and repair_commands.py with the unused dependency_rows parameters removed from src/cadrumo/application/preflight.py and diagnostics.py, and tests`.
- [x] `P07.S21` - Add the setup, model, runtime and Google sign-in operator actions; `src/cadrumo/application/operator_actions/catalogue.py and tests`.
- [x] `P07.S22` - Add the TUI setup screen with item rows, plan review through the operation modal, progress, recovery actions and the Google sign-in hand-off; `src/cadrumo/entrypoints/tui/setup/, the TUI navigation registration (src/cadrumo/entrypoints/tui/navigation.py, search.py, src/cadrumo_runtime/host/frontend/tui/runtime_workbench.py), the cue-only operation modal (src/cadrumo/entrypoints/tui/operations/modal.py, principal-approved), and tests`.
- [x] `P07.S23` - Relay setup progress with its subject as MCP progress notifications, update the surface facts for the added and removed operations, and hold parity in tests; `src/cadrumo_harness/mcp/ and its tests`.

### Phase `P08` - Smoke and verification gates

Lane H adds the cross-cutting gates: registry conformance, transfer fault injection against real local servers, the bounded quick check, developer doctor reuse, the packaged setup acceptance, and live acceptance on a disposable host.

- [x] `P08.S24` - Add the registry conformance gate: every item has quick and full checks, wording in four languages and a recovery action, and every surface reads the registry; `src/cadrumo/application/tests/test_dependency_registry_conformance.py`.
- [x] `P08.S25` - Add transfer fault tests against real local HTTP and TLS servers for reset, timeout, 5xx, 429, truncation, slow transfer, disk full and interruption with resume; `src/cadrumo/application/tests/test_dependency_transfer_faults.py`.
- [x] `P08.S26` - Point the developer doctor and a just recipe at the registry checks, and add a quick-check time bound test; `dev/env/playwright_doctor.py, justfile doctor recipes, src/cadrumo/entrypoints/tests/test_dependency_quick_check_bound.py (moved from application/tests: the composed registry lives in entrypoints, which application tests may not import)`.
- [ ] `P08.S27` - Packaged isolated-root setup acceptance on the development host: drive the staged packaged app against a throwaway storage root under build/windows-x64/testing (browser setup with review, forced interruption and Resume, the app's own full check, a no-op second run, verified cleanup and an unchanged real storage); a true vanilla-machine run stays pending because the user has no disposable host and declined machine changes (2026-10-18); `native/desktop/tests/packaged/setup.mjs, native/desktop/tests/packaged.test.mjs`.
- [x] `P08.S28` - Add the isolated-environment acquisition lane: a vanilla-machine stand-in that runs the real browser acquisition end to end in one throwaway root under build/windows-x64/testing, with env overrides, a before/after listing of real storage, a free-space floor of required_free_bytes plus 10 GiB, a byte budget that aborts mid-run, opt-in model items, resume, transient retry, offline refusal, the full check, a no-op second run, and verified cleanup of the root and any keychain entries; `dev/smoke/acquisition_lane.py, dev/smoke/tests/test_acquisition_lane.py`.

## Parallelization

Eight lanes, one per Phase. Each lane runs one Opus implementer with its own haiku fleet. All lanes work in the shared `tui` worktree; nobody creates a worktree or a snapshot checkout. A lane writes only inside its write set. A needed change outside it goes to the owning lane through the orchestrator. Each lane commits only its own paths with plain `git add <paths>` and `git commit`, one commit per Step, and logs its rows with `vaultspec-core vault exec log --feature dependency-provisioning --step <S##> --related 2026-10-18-dependency-provisioning-plan`. Shared files are re-read before every patch, and formatters and linters run on literal path lists only.

**Hard ordering.** P01.S01 lands first: it publishes the registry contracts and the progress subject that every lane imports. P05.S14 lands before P06 consumes the Host port. Everything else may start once those two have landed, and may begin earlier against the declared shapes when they are agreed in the orchestrator thread.

- **Lane A, P01 (mechanism).**
  - Writes: `src/cadrumo/application/dependency_*.py` (new); `src/cadrumo/application/operations/persistence/events.py` and `frontend_requests.py` (progress subject only); `src/cadrumo/application/operations/access_facts.py`; `src/cadrumo/core/external_constants.toml` (dependency hosts section); `src/cadrumo/core/storage_taxonomy.py` and `storage_taxonomy_locations.py` (receipts category only); `src/cadrumo/entrypoints/dependency_operation_composition.py` (new); `src/cadrumo/entrypoints/local_reader_operation_composition.py`; `src/cadrumo/entrypoints/operation_composition.py` (registration lines only); `src/cadrumo/application/preflight.py`; `src/cadrumo/application/diagnostics.py`; the `provisioning` subtree of `src/cadrumo/locales/*/application.yml`; and tests under `src/cadrumo/application/tests/` and `src/cadrumo/entrypoints/tests/` named `test_dependency_*`.
  - Depends on nothing. It defines the item provisioner protocol that lanes B, C and D implement, and calls their provisioners through the registry, never by importing their internals.
  - Verify: `uv run --no-sync pytest src/cadrumo/application/tests -k dependency -q`, `just check-operation-contract-manifest`, `just check-locales`, `uv run --no-sync lint-imports --config .importlinter --no-cache`, and `just check-types` on the touched modules.
- **Lane B, P02 (local model).**
  - Writes: `src/cadrumo/application/provisioning.py`, `provisioning_runtime.py`, `provisioning_host.py`, `provisioning_fitness.py` and `provisioning_contracts.py`; `src/cadrumo/application/local_reader*.py`; `src/cadrumo/core/model_catalogue.py`; `src/cadrumo/adapters/outbound/model_runtime/`; `src/cadrumo/adapters/outbound/llm/role_fitness.py`; `src/cadrumo/entrypoints/tests/registered_executor_*.py` (local-reader cases only); and their tests.
  - Depends on P01.S01, and on P01.S04 for the end-to-end setup path.
  - Verify: `uv run --no-sync pytest src/cadrumo/application/tests -k "provisioning or local_reader" -q` against injected measurements and a real local HTTP server. No agent pulls, loads or runs a GPU model during development (`2026-08-07-unstructured-document-ingestion-provisioning-adr` constraint).
- **Lane C, P03 (browser).**
  - Writes: `src/cadrumo/application/provisioning_browser.py`; `src/cadrumo/application/browser_runtime_operation.py` (deletion); `src/cadrumo/adapters/outbound/browser_runtime/`; and their tests.
  - Depends on P01.S01. The deletion in P03.S11 lands only after P01.S04 has removed the registration and P07.S20 has moved the CLI.
  - Verify: `uv run --no-sync pytest src/cadrumo/application/tests -k browser -q` and `just doctor-browser`.
- **Lane D, P04 (Google).**
  - Writes: `src/cadrumo/adapters/outbound/google/`; `src/cadrumo/entrypoints/google_configuration_operation_composition.py`; `src/cadrumo_runtime/commands/google.py` and `google_auth_specs.py`; and their tests.
  - Depends on P01.S01.
  - Verify: `uv run --no-sync pytest src/cadrumo/adapters/outbound/google src/cadrumo_runtime/commands -k google -q`. The live refresh and root-folder read run once, by a person, on a test account. They are never automated.
- **Lane E, P05 (desktop host and person bridge).**
  - Writes: `native/desktop/frontend/src/ipc/contract.ts` (setup section); `native/desktop/frontend/src/shell/host.ts` and `tauriHost.ts` (setup methods); `src/cadrumo_runtime/host/session_hold.py` and its tests; `native/desktop/src-tauri/src/shell/setup/` (new); `native/desktop/src-tauri/src/agent/person.rs` (pushed event only); `native/desktop/src-tauri/src/app.rs` (command registration only).
  - Depends on P01.S04 for the operations that S15 calls, and on P04.S13 for sign-in.
  - Verify: `uv run --no-sync pytest src/cadrumo_runtime/host -k session_hold -q`; `cargo test` for the desktop crate, run small and serial and agreed with the live build session first; rustfmt through stdin only; and `npm run check` in `native/desktop/frontend`.
- **Lane F, P06 (desktop frontend).**
  - Writes: `native/desktop/frontend/src/components/setup/` (new); `native/desktop/frontend/src/components/Settings.tsx`, `Rail.tsx` and `App.tsx` (setup actions, prompts, badge and toasts only); the scenario host modules under `native/desktop/frontend/src/shell/`; stories; `dev/locales/desktop_chrome.py` (setup keys); and the `desktop.setup` subtree of `src/cadrumo/locales/*/common.yml`.
  - Depends on P05.S14 for the Host port. It builds against the scenario host before the real host lands.
  - Verify: `npm run check` and `npm run test` in `native/desktop/frontend`; `npm run storybook:build`; `just check-locales`; and theme-driven styling only, with no hand-styled elements.
- **Lane G, P07 (CLI, TUI and MCP parity).**
  - Writes: `src/cadrumo/entrypoints/cli/config/provision_cli.py` and `_provision_command_specs.py`; `src/cadrumo/entrypoints/cli/command_operation_table.py` (provision rows only); the `provision` subtree of `src/cadrumo/locales/*/cli.yml`; `src/cadrumo/application/operator_actions/catalogue.py` (provision entries only); `src/cadrumo/entrypoints/tui/setup/` (new) with its navigation registration line; `src/cadrumo_harness/mcp/`; and their tests.
  - Depends on P01.S04, P02.S09, P03.S10 and P04.S13.
  - Verify: `uv run --no-sync pytest src/cadrumo/entrypoints/cli src/cadrumo/entrypoints/tui src/cadrumo_harness -k "provision or setup or parity" -q`, the parity tests of `src/cadrumo_harness`, and `just check-operation-contract-manifest`.
- **Lane H, P08 (gates).**
  - Writes: the three new test modules named in P08; `dev/env/playwright_doctor.py`; the doctor recipes in `justfile`; and `native/desktop/tests/packaged/setup.mjs`.
  - Depends on every other lane for green runs. It authors its gates early against P01.S01, and those gates are expected to fail until the lanes land.
  - Also writes, for P08.S27: `native/desktop/tests/packaged.test.mjs` (the setup suite selector only).
  - Verify: its own gates. P08.S27 never touches a development machine's real storage root: as amended 2026-10-18 it runs on the development host against one throwaway root under `build/windows-x64/testing`, and a vanilla-machine run stays pending until a disposable host exists.

## Verification

Fast smoke checks, run in this order, each failing on its own:

- **Quick check bound.** `aeat config provision status` (the quick mode of `dependencies.status`) answers every item within 2 s on a clean storage root and on a provisioned one, with no network and no model load (`test_dependency_quick_check_bound.py`).
- **Registry conformance.** Every item declares quick and full checks, wording in four languages and a recovery action. The CLI, TUI, MCP and desktop renderers read the registry and no private list (`test_dependency_registry_conformance.py`).
- **Transfer faults.** Real local HTTP and TLS servers produce reset, timeout, 5xx, 429, truncation, slow transfer and a full disk. Retries stop at the declared budget, a transient fault never surfaces as a permanent category, and an interrupted transfer resumes rather than restarting (`test_dependency_transfer_faults.py`).
- **Approval binding.** A setup whose plan changes after approval refuses. CLI without `--yes` in a non-interactive shell refuses with the approval sentence. MCP answers the same review and gets the same effect.
- **Truthful states.** A marker without the executable is not ready, a missing Google token is not signed in, an unreadable probe is unknown, and a receipt alone never yields ready.
- **Developer doctor.** `just doctor-browser` and `just doctor-product` report through the registry's full check.
- **Desktop scenarios.** The browser suite covers every state, failure category and phase of the setup dialog, Components section, prompts, badge and palette actions. No internal code or term appears in rendered text, which a test asserts against the category list.

Plan-level criteria:

- No `config provision` leaf maps to no operation, and no CLI path downloads in process (`src/cadrumo/entrypoints/cli/command_operation_table.py`).
- `browser-runtime.provision` and the download actions of `local-reader.provision` no longer exist anywhere, with no aliases.
- Import contracts, style, format, types and locale checks pass on the touched scope: `uv run --no-sync lint-imports --config .importlinter --no-cache`, `just check-style`, `just check-format`, `just check-types`, `just check-locales`.
- Packaged acceptance (P08.S27), amended 2026-10-18 because no disposable host exists and the user declined machine changes: on the development host, from a clean throwaway storage root, one approval sets up the browser, verifies it with the app's own full check, survives a forced interruption with Resume and no second review, and a second setup changes nothing. The model runtime and the default models are opt-in for this run. Google sign-in is completed by a person. Each item's evidence is recorded separately; authored metadata alone is not evidence. The vanilla-machine run stays pending.
- New regressions are reported separately from the known failures recorded for this worktree.

The plan is complete when every Step is closed and the integrated review at each Phase close and at plan close passes. Review traces the whole flow (registry, operation, bridge, each front end) against the ADR. It is not a per-file review.
