---
tags:
  - '#reference'
  - '#dependency-provisioning'
date: '2026-10-18'
modified: '2026-10-18'
body_schema: 'body-v2'
body_hash: 'sha256:78b6c4ea57e5680e3891f0b49fa22db2c99542497d1e0900bc5d4f0d40336faa'
related:
  - "[[2026-06-15-dependency-provisioning-adr]]"
---

# `dependency-provisioning` reference: `Provisioning mechanisms for the local model, browser and Google`

Maps how Cadrumo provisions, checks and reports its three runtime dependencies as of 2026-10-18 in the `feature/tui` worktree: the local model (model runtime plus per-role weights), the Playwright Chromium browser, and Google sign-in. Sources were read directly, with semantic and grep discovery over `src/cadrumo/application`, `src/cadrumo/adapters/outbound`, `src/cadrumo/entrypoints`, `src/cadrumo_runtime`, `src/cadrumo_harness`, `src/cadrumo_client` and `native/desktop`. The governing decisions read in full are listed in the ADR `2026-10-18-dependency-provisioning-unified-setup-adr`. Locators are observations to re-check against current code before an edit.

## Summary

### Shared probe and outcome shape

- `DependencyStatus` (`src/cadrumo/application/provisioning.py:116`) is the doctor row: service, available, detail, remediation. Probes never raise on absence. `aeat config check` renders them through `src/cadrumo/application/preflight.py:1-19`.
- Provisioning outcomes carry a typed `PreconditionVerdict` keyed by `ProvisioningPreconditionCondition` (`src/cadrumo/application/provisioning_contracts.py:73-107`); `require_provisioning_verdict` (`:130`) refuses a failure without one.
- Fixed timeouts: probe 2 s (`provisioning_contracts.py:29`), pull 3600 s (`:52`), readiness 120 s (`:57`), runtime start 30 s (`:61`), runtime install 1800 s (`:70`), keep-alive 30 m (`:67`).
- The health report in `src/cadrumo/application/diagnostics.py:262-302` (`build_config_repair_report`, statuses OK, WARN and FAIL with a mandatory verdict, `:13-16`) has no model, browser or Google row.

### Local model

- Catalogue: `MODEL_CATALOGUE` at `src/cadrumo/core/model_catalogue.py:424-538`, defaults `:540-553`. Entries are Ollama tags with a memory figure, context window and licence (`:208-299`); none pins a content digest.
- Selection: `select_model_for_role` (`src/cadrumo/application/provisioning.py:715-822`) takes the smallest candidate that clears the context, licence and headroom bars.
- Runtime program: installed only with consent, through winget `Ollama.Ollama` or Homebrew (`src/cadrumo/application/provisioning_host.py:440-507`, `src/cadrumo/adapters/outbound/model_runtime/process_control.py:59-98`; installer output is discarded). `start_runtime` (`provisioning_host.py:360`) launches `serve` with `OLLAMA_HOST` and `OLLAMA_MODELS` (`:305`, `:322`), enforces loopback (`:292`) and polls every 0.5 s until reachable (`:71`).
- Pull: `pull_runtime_model` (`src/cadrumo/application/provisioning_runtime.py:863`) admits memory before any byte moves (`:905-924`), streams `POST /api/pull` NDJSON (`:954-975`) into `PullProgress` (`:780`), and succeeds only on a `status == success` line (`:976-1019`). Resuming partial blobs is the runtime's own behaviour; Cadrumo adds none.
- Admission: `assess_model_load_contention` (`provisioning_runtime.py:364-507`) fails closed on an unreadable free-memory figure or resident set.
- Verification: `verify_model_ready` (`provisioning_runtime.py:1088-1179`) reads `/api/ps`, then `/api/tags`, then sends a one-token generate. That cold-loads a non-resident model with the default keep-alive, not the explicit load's 30 m. A role fitness probe follows (`src/cadrumo/application/local_reader.py:235-278`, `src/cadrumo/adapters/outbound/llm/role_fitness.py:63`); verdicts bind endpoint, model, runtime digest and role (`src/cadrumo/application/provisioning_fitness.py:60-69`).
- Integrity: Cadrumo checks no hash or size. The runtime digest from `/api/tags` (`provisioning_runtime.py:1182-1197`) keys only the fitness verdict.
- Storage: weights at `models/ollama`, runtime home at `components/ollama/home` (`src/cadrumo/core/storage_taxonomy_locations.py:96-114`), both under the storage root and shared by every profile.
- Operations: `local-reader.provision` with actions install, start, pull, load, verify, remove and setup (`src/cadrumo/application/local_reader_contracts.py:72-81`). Install and setup take a boolean `consent` (`:107`, `:119-140`). Setup publishes a phase code per step (`:103-105`) and progress through `_ProgressRelay` (`src/cadrumo/application/local_reader_provisioning.py:112-135`). `local-reader.status` and `local-reader.report` are reads (`src/cadrumo/entrypoints/local_reader_operation_composition.py:63-90`).

### Browser

- Required builds come from the bundled Playwright package's `driver/package/browsers.json`: `chromium` and `chromium-headless-shell` (`src/cadrumo/application/provisioning_browser.py:67-70`, `:128`, `:157`). Entries with `revisionOverrides` read as unreadable (`:149`).
- Location: `playwright_browsers_root` (`provisioning_browser.py:93-120`); default category `PLAYWRIGHT_BROWSERS` at `components/playwright` (`src/cadrumo/core/storage_taxonomy_locations.py:146-153`), shared by every profile.
- Presence probe: one completion marker per build directory (`provisioning_browser.py:201-237`); no launch, version or content check.
- Install: `install_playwright_browser` (`provisioning_browser.py:268`) is idempotent, runs `python -m playwright install chromium` for up to 1800 s and decides success by re-probing (`:282-309`). The installer discards stdout and stderr (`src/cadrumo/adapters/outbound/browser_runtime/installer.py:38-46`), so there is no byte progress and no failure detail. No proxy is passed.
- Launch: `src/cadrumo/adapters/outbound/aeat/browser/factory.py:444-458` sets `PLAYWRIGHT_BROWSERS_PATH`; `session.py:218-240` refuses with `BROWSER_NOT_PROVISIONED` before Playwright runs. The AEAT proxy settings (`src/cadrumo/core/config.py:540-555`, `session.py:204-216`) reach the launched browser only.
- Operation: `browser-runtime.provision` (`src/cadrumo/application/browser_runtime_operation.py:105-165`): durability recorded, cancellation unsupported, idempotent submit, reconciliation interrupt, phase events only (`:120-125`), effect `PARTIAL` when the installer ran and failed (`:96-102`).
- Recovery action: `operator.provision.browser` (`src/cadrumo/application/operator_actions/catalogue.py:457-460`) is the only `operator.provision.*` entry. No entry exists for the model or the runtime program.
- Developer doctor: `dev/env/playwright_doctor.py:51-76` performs a real headless launch, which the product probe does not.

### Google

- Client identity is a package fact: `src/cadrumo/core/config_google.py:13-74` reads the installed `google/oauth_client.json` and ignores environment input; `src/cadrumo/adapters/outbound/google/installation_client.py:32-54` raises `GoogleAuthClientMetadataUnavailableError` when it is absent or invalid. Build input: `dev/packaging/google_oauth.py:31-83`.
- Sign-in: `run_login_flow` (`src/cadrumo/adapters/outbound/google/oauth_flow.py:231-292`) with PKCE and a loopback receiver on `127.0.0.1` (`oauth_flow.py:324-355`, `oauth_callback.py:18-99`), 300 s timeout (`oauth_flow.py:67`). It requires an interactive terminal (`oauth_flow.py:278`, guard `:70-96`), so no desktop or TUI path can start it today.
- Scopes: `openid`, `userinfo.email`, `drive.file` (`src/cadrumo/core/external_constants.toml:307-310`, `adapters/outbound/google/records.py:34-45`). `credentials_to_records` accepts a superset (`oauth_flow.py:206-214`) while `_oauth_loopback_records` requires equality (`:613-623`).
- Custody: token SECRET and metadata FINANCIAL, profile-local (`src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:868-895`); save and delete run in one batch each (`adapters/outbound/google/session_store.py:58-184`). Client binding and ended-grant mapping: `sign_in_state.py:30-100`.
- Status: `config.google.status` reads metadata only (`sign_in_state.py:76-95`, `src/cadrumo/entrypoints/google_configuration_operation_composition.py:306-315`), so a profile whose token row is gone can report signed in. No status step refreshes the token or reads the Drive root.
- Upstream errors are classified by substrings such as "network" (`oauth_flow.py:397-432`) behind a broad catch (`:373-374`).
- Command ownership: login, status and logout are runtime commands (`src/cadrumo_runtime/commands/google_auth_specs.py:116-149`); folder and probe are tax CLI commands (`src/cadrumo/entrypoints/cli/config/_google_command_specs.py:116-150`). Both declare the `config google` group (`:117` in each).

### Registered operations, progress and interactions

- Lifecycle and effects: `src/cadrumo/core/operations.py:8-18`, `:68-85`. `UNKNOWN` is an effect value, set when an executor was entered and its outcome is uncertain (`src/cadrumo/application/operations/_supervisor_reconciliation.py:117`, `:179`).
- Progress event: `completed`, `total > 0`, `unit_code` (`src/cadrumo/application/operations/persistence/events.py:52-64`; public mirror `frontend_requests.py:483-497`). It names no subject, so a multi-item setup cannot say which item a figure belongs to.
- Delivery: journal commits cue observers through `operation_changed` (`2026-10-17-idle-churn-operation-observation-adr`). The TUI modal still polls every 200 ms (`src/cadrumo/entrypoints/tui/operations/modal.py:73`, `:264`). MCP observes once per tool call (`src/cadrumo_harness/mcp/admitted_operations.py:394-406`).
- Interactions: INPUT, CHOICE, REVIEW, APPLY, REJECT (`src/cadrumo/core/operations.py:153-160`). Responses are digest-bound and single-use (`src/cadrumo/application/operations/interactions.py:29-172`). Cancellation is refused inside irreversible sections (`_execution_context.py:82-117`).
- Deadlines: execution 1 h, cleanup 2 min (`src/cadrumo/entrypoints/operation_composition.py:100-101`). CLI settlement waits 3600 s and reports still-running with its identity (`src/cadrumo_client/commands/registered_operation_observations.py:67-86`).

### Front ends

- CLI: every `config provision` leaf maps to no registered operation (`src/cadrumo/entrypoints/cli/command_operation_table.py:349-359`). The verbs run provisioning in the CLI process: `provision_browser` calls `install_playwright_browser` directly (`src/cadrumo/entrypoints/cli/config/provision_cli.py:136-144`), and the others call `provision_local_reader` through `asyncio.run` (`provision_cli.py:214-230`). The CLI path therefore skips the journal and effect accounting that the TUI and MCP path gets.
- TUI: no provisioning or Google sign-in screen exists under `src/cadrumo/entrypoints/tui`.
- MCP: operations are listed from the session's effective scope, leaving out person acts (`src/cadrumo_harness/mcp/operation_discovery.py:28-91`).
- Desktop: the palette registry is `native/desktop/frontend/src/shell/actions.ts:1-47`, with entries in `App.tsx:866` onward. Settings is one popover section of window preferences (`components/Settings.tsx:72-172`). There is one toast slot (`App.tsx:227`, `:461-465`). The host reaches the runtime only through the closed actions of the held person bridge (`native/desktop/src-tauri/src/agent/person.rs:82-120`, served by `src/cadrumo_runtime/host/session_hold.py:228-307`), whose pushed events are language, attendance and retirement only (`person.rs:43-62`). The desktop has no setup, model, browser or Google surface.

### Network

- The only proxy settings are the AEAT browser's `CADRUMO_PROXY_*` (`src/cadrumo/core/config.py:540-555`). No download path passes a proxy, reads the system trust store or checks reachability before it starts.
- `src/cadrumo/application/connectivity_probe.py:1-18` probes the tax agency's public landing page only (`diagnostics.connectivity.probe`).

## Gaps and inconsistencies

- The CLI and the registered operation are two paths for the same act, with different journaling.
- Nothing verifies content after a download for the browser or the model; browser readiness is a marker file.
- Cadrumo has no retry, backoff or resume logic; a failed browser install restarts every build.
- No free-disk check runs before a multi-gigabyte download.
- The browser has no byte progress, and progress events carry no subject.
- Consent is a request boolean, not bound to what will be downloaded.
- Google status can report signed in with no usable token, and sign-in is terminal-only.
- Readiness is spread over `config check`, `config provision status`, `local-reader.status` and `config google status`, with no single state per dependency and no health-report row.
- Only the browser has a recovery action in the operator catalogue.
- The readiness probe cold-loads although it reads as a residency check, with a different keep-alive from the explicit load.
- Catalogue tags are mutable upstream names with no expected digest.
- `2026-08-07-unstructured-document-ingestion-provisioning-adr`, whose lifecycle the code implements, is still `proposed`. Its D5 statement that the runtime is never spawned differs from the shipped install and start actions.
