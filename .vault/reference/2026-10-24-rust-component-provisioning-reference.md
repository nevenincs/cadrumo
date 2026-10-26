---
tags:
  - '#reference'
  - '#rust-component-provisioning'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:16a7628a8c439ccb267885091fb7062764cc733d69e3742b610ece7488394a1b'
related:
  - "[[2026-10-18-dependency-provisioning-unified-setup-adr]]"
  - "[[2026-10-18-dependency-provisioning-mechanisms-reference]]"
---

# `rust-component-provisioning` reference: `Component provisioning ownership, on-demand gating and AI backend as of 2026-10-24`

Static reading of the `feature/tui` tree on 2026-10-24. The owner asked whether product component provisioning (Playwright Chromium and the local AI) is managed entirely by Rust with no Python, whether a feature that needs a missing component tells the person, and how the AI backend is integrated. Discovery used `vaultspec-rag` code and vault searches plus targeted grep; the principal re-read every load-bearing locator below. Nothing was built, run or tested. It supersedes the stale parts of `2026-10-18-dependency-provisioning-mechanisms-reference`, which still describes `browser-runtime.provision` and the download actions of `local-reader.provision`, both removed.

## Summary

### Verdict: provisioning is Python-owned; Rust only relays

Every download, install, verification and readiness decision runs in Python under the registered `dependencies.setup` operation, as `2026-10-18-dependency-provisioning-unified-setup-adr` D1 and D3 decide. The desktop host projects it over the held Python person session.

- Registry and items: `src/cadrumo/application/dependency_registry.py:65-85` declares `browser` and `local_ai`, with recovery actions `operator.provision.browser` and `operator.provision.local_ai`; item kinds at `src/cadrumo/application/dependency_contracts.py:111-122`; operation ids and registration at `src/cadrumo/application/dependency_setup_operation.py:170-177` and `src/cadrumo/entrypoints/dependency_operation_composition.py`.
- Browser: `src/cadrumo/application/provisioning_browser.py` reads the installed Playwright package's `browsers.json` (`required_browser_builds`, around line 157), probes the revision-exact build and its completion marker (around 284-325) and drives the vendor installer. `src/cadrumo/adapters/outbound/browser_runtime/installer.py` runs `playwright install chromium` (the Node driver in the `playwright` wheel) against a loopback server (`archive_server.py`) that serves only archives fetched by `archive_fetch.py` and matched to `src/cadrumo/_data/dependencies/browser_archives.toml` pins (`src/cadrumo/application/browser_archive_pins.py`). Headless launch check: `browser_runtime/launch_check.py`.
- Local AI program: `src/cadrumo/application/provisioning_host.py` locates Ollama in standard paths (around 110-124), finds winget or Homebrew (around 151) and starts the server with `OLLAMA_HOST`, `OLLAMA_MODELS` and `OLLAMA_HOME` from storage categories (around 285-358). `src/cadrumo/adapters/outbound/model_runtime/process_control.py:79-110` runs `winget install --id Ollama.Ollama --exact --silent ...` or `brew install ollama` through `subprocess.run`; Linux keeps a manual instruction.
- Models: `src/cadrumo/application/provisioning_runtime.py` streams `POST /api/pull` to the running Ollama, loads with `keep_alive`, lists with `/api/tags`; registry host `registry.ollama.ai` (`provisioning_contracts.py:80`). Pins and defaults: `src/cadrumo/core/model_catalogue.py` (`ModelWeightsPin` near 255, `DEFAULT_MODEL_BY_RUNTIME_AND_ROLE` near 540; qwen3-vl:2b for vision, qwen3:1.7b for the text roles).
- Storage: `src/cadrumo/core/storage_taxonomy.py:220-225` (`PLAYWRIGHT_BROWSERS`, `OLLAMA_MODELS`, `OLLAMA_HOME`, `CHROMIUM_DATA`) and the receipts category from the unified-setup ADR D12; browser override `CADRUMO_PLAYWRIGHT_BROWSERS_DIR` (`provisioning_browser.py` near 173).
- Desktop relay: `native/desktop/frontend/src/shell/tauriHost.ts:232-258` maps `setup.*` to `desktop_setup_*` commands in `native/desktop/src-tauri/src/shell/setup/mod.rs:305-404`, which exchange through `PersonRelay`/`HeldPerson` (`mod.rs:86-95`, `136-218`). `shell/setup/track.rs` turns window actions into generic relay requests (`operation_submit`, `operation_observe`, `operation_review`, `operation_respond`, `operation_cancel`) naming `dependencies.status`, `dependencies.verify` and `dependencies.setup` (`track.rs:25-30`). The held person session is a Python child.
- Removed paths confirmed absent: `src/cadrumo/application/browser_runtime_operation.py` does not exist; `browser-runtime.provision` survives only in test assertions.
- Dev-only Python that downloads outside the registry: `dev/env/playwright_setup.py` (direct `python -m playwright install`). `dev/env/playwright_doctor.py` and `dev/smoke/acquisition_lane.py` reuse the registry adapters.

### What Rust already has

- `native/application/src/component.rs` is a generic, unused component store: `Artifact` with id, revision, target, SHA-256, archive size and unpack limits (`:21-62`); `Cancellation` (`:65-77`); `ComponentStore::provision` with target admission, a non-unlinked writer lock, staging, a per-file digest receipt and an active-pointer cutover (`:194` onward); zip extraction with entry and size bounds (`:386`); `download_and_activate` over `ureq` with HTTPS only and a 300 s global timeout (`:325-350`). Its only caller is `native/application/tests/application.rs:765`. It has no proxy, no progress callback, no resume, no retry and no redirect-host policy.
- `native/application/src/python.rs` `BrowserQuery` (`:45-49`) asks the Python interpreter where the browser is ("None delegates storage resolution to the Python settings owner").
- Crates: `native/application/Cargo.toml` carries `sha2`, `zip` (deflate), `ureq` 3 with rustls and `tokio`; no `tar`, `flate2` or `zstd`.
- The native Rust runtime client (`native/platform/src/runtime_pipe.rs`, `native/application/src/runtime_client.rs`) already signs in and reads status on the window's own connection; the operation relay is the remaining Python child.
- Package assembly already reads the staged pin table and refuses a package whose pins do not cover the staged driver's Chromium builds (unified-setup ADR, 2026-10-21 amendment).

### On-demand gating: browser yes, models no

- Browser, verified: `src/cadrumo/adapters/outbound/aeat/browser/session.py:218-248` calls `_require_bundled_browser_provisioned()` before any Playwright launch; failure raises `BrowserError` with `failure_mode=browser_not_provisioned` and a verdict carrying `operator.provision.browser` (`provisioning_browser.py:259-275`). The error code is the generic `FAIL_BROWSER_SESSION_BROWSER`. MCP surfaces `recovery_action_id` (`src/cadrumo_mcp/mcp/protocol_contract.py:368`); the desktop opens the setup prompt only for agent tool refusals (`native/desktop/frontend/src/App.tsx:737-751`, `native/desktop/src-tauri/src/agent/stream.rs:51-88`). The CLI prints raw `precondition_action.*` lines (`status_rendering.py:52-70`); the TUI modal prints a command string with no jump to the Setup screen (`run_result.py:54-72`). The guard runs at launch, not at operation start.
- Models, verified: `probe_local_reader` (`src/cadrumo/application/local_reader.py:422-486`) distinguishes runtime unreachable, no model selected and role model not installed, but builds all three with `provisioning_no_recovery_verdict` (`local_reader.py:457`, `467`, `477`; `provisioning_contracts.py:123-136`), an `OPERATOR_DECISION` no-action verdict. Nothing outside the registry and the operator catalogue emits `operator.provision.local_ai`. So MCP's `recovery_action_id` is null, the desktop never routes to setup, and CLI and TUI print no action.
- The reader probe runs only after a failure: `invoice_draft_extraction.py:900-925`, `ledger_llm_composition.py:150-163` (falls back to a generic `LLMClassifierError` when no verdict), `batch_ingest.py:495-519` (the only pre-check; it pauses with the verdict).
- Silent paths: `resolve_column_roles` in `src/cadrumo/adapters/outbound/llm/column_role_mapping.py` catches every `CadrumoError` and returns `None` (around 685-688), so a missing model declines the table with only a log line. The label-first draft fallback says "could not start ... extract again later" without naming the model or setup (`locales/en/cli.yml:256`). The supply-nature proposal checks catalogue and hardware fitness only.
- Desktop non-agent refusals: `native/desktop/frontend/src/shell/ledger.ts:215-223` types `precondition_verdict_json`, but no component reads it; the Readers tab shows "not ready" with no setup action.
- Explicit setup surfaces are complete: CLI `aeat config provision *` and `config check`, TUI `src/cadrumo/entrypoints/tui/setup/`, desktop first-run dialog and Settings advisory, all on the `dependencies.*` operations.

### AI backend integration

- Supported and present: the tax side holds no vendor adapters (`LLMProvider` is `{AGENT, LOCAL}`, `src/cadrumo/core/config_support.py:90-110`); hosted runs go worker to runtime to agent service to a cadrumo-agent background run (`src/cadrumo/application/operations/model_runs.py`, `src/cadrumo_runtime/host/profile_connection_model_runs.py`, `src/cadrumo_agent_service/host/model_run_relay.py`, `src/cadrumo_agent_service/providers/application/model_runs.py`); per-profile provider keys live in the agent service store and reach the agent on a stdin frame (`src/cadrumo_agent_service/host/credential_frame.py`); providers and models come from cadrumo-agent's catalog (`adapters/agent_provider_catalog.py:44`); local inference is Ollama through `adapters/outbound/llm/providers/local.py`; the off-host consent ledger binds evidence extraction (`src/cadrumo/adapters/persistence/llm/consent_ledger.py`).
- Conflicting:
  - `src/cadrumo_agent_service/providers/application/model_runs.py:73-90` discards `role` and picks the first catalog lane with a default model, so a tax run can land on a lane the person never chose.
  - `src/cadrumo_agent_service/providers/application/resolution.py:14-17` keeps the `CADRUMO_LLM_<ID>_API_KEY` development fallback that the owner ruled legacy.
  - `src/cadrumo/core/model_catalogue.py:127-131`, `566` and `601-605` keep a `CLOUD_ANTHROPIC` runtime with a hardcoded `claude-haiku-4-5` for every role and no consumer, against the rule that Claude model ids come from the Models API.
  - The desktop-agent-host ADR family is still `proposed` and describes a removed `aeat app agent serve` launcher.
- Missing: per-role lane selection storage, UI and lookup; a desktop or TUI control for the on-host versus agent choice (only `ledger.evidence.extract` takes `off_host_provider`); hosted routes for classification, statement reading and ingestion (all pinned `LOCAL`); confirmed encryption of agent attachment content (an agent-repo question).

### Interfaces a Rust provisioner must honour

- Python Playwright launches Chromium at use time (`session.py`), so a Rust provisioner must write the exact browser layout the bundled driver expects under the browsers root: one directory per build named in `browsers.json`, the executable path inside it, and the completion marker. The pins table already records each archive's build directory, path, sources, size and SHA-256.
- Python inference talks to Ollama over loopback HTTP; it needs the program's location, the server address and the models root, which today come from `provisioning_host.py` and the storage taxonomy.
- Surfaces read the item rows, wording, plan review, phase and progress events and closed failure categories decided in unified-setup ADR D2, D4, D5 and D9. The wording lives in the canonical locale catalogues.
