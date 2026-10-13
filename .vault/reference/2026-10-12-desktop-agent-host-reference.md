---
tags:
  - '#reference'
  - '#desktop-agent-host'
date: '2026-10-12'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:1bd17050732b00417d1c91f7bfbe24eec19aaa4ba0d103d37269981d0e06862a'
related: []
---

# `desktop-agent-host` reference: `Hosting cadrumo-agent from the desktop: verified contract`

What the desktop would build on if it hosts the cadrumo-agent service for the agent column, checked against code rather than plan checkmarks or route lists. Three read-only audits ran on 2026-10-12: this repository's desktop shell, sign-in and MCP admission; this repository's document custody; and the cadrumo-agent checkout at `Y:\code\cadrumo-agent-worktrees\main` (package `0.1.0`, no commit pinned). Paths prefixed `agent:` are in that checkout. No test was run in either repository; "tested" below means a test was read and exercises the real component. cadrumo-agent's API route tests cannot pass today: `agent:src/cadrumo_agent/api/tests/conftest.py:40-60` fails `make_app()` unconditionally, and 740 tests carry the `capability_gap` fail-stub marker enforced at `agent:src/cadrumo_agent/conftest.py:700-712`.

## Summary

### Classification legend

Implemented: code exists. Verified: a real-component test covers it. Gated: implemented but unreachable in any configuration that starts. Missing: no code.

### cadrumo-agent: hosted startup and the Cadrumo tool relay

- Hosted mode is gated. `CADRUMO_AGENT_HOSTED_ROOT` switches it on (`agent:src/cadrumo_agent/providers/lane_registry.py:148-155`), and startup then requires recorded tool-access and tool-write proofs for the `cadrumo` tool server. Both proof sets are empty (`agent:src/cadrumo_agent/providers/lane_admission.py:478-484`, `:551-570`), so every hosted start exits 78 with `hosted_tool_server_unproven` (`agent:src/cadrumo_agent/api/app.py:144-197`). Nothing in product code bypasses it.
- No real, signed-in Cadrumo tool call is recorded. The only end-to-end test is a fail-stub (`agent:src/cadrumo_agent/service_tests/test_assembled_hosted_parts.py:310-321`); the stand-ins it used were deleted.
- The relay entry launches `cadrumo-mcp --surface full` with no credential and no profile argument (`agent:src/cadrumo_agent/providers/_harness_mcp_registry.py:375-420`) and demands an exact list of 18 tools, including `authenticate`, `authorization_*`, `installation` and `session` (`agent:src/cadrumo_agent/providers/_mcp_contract.py:256-273`). This repository's `full` surface serves 12 (`src/cadrumo/application/operations/mcp_surfaces.py:101-116`, `:136-143`), so the mount would be refused against this build, and those credential-shaped tools conflict with `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`.
- Host start contract (implemented): environment `CADRUMO_AGENT_HOSTED_ROOT`, `_PORT`, `_WORKER_PORT`, `_HOSTED_CLI_EXECUTABLE`, `_HOSTED_PYTHON_EXECUTABLE`, optional `_ANTHROPIC_API_KEY`; verb `serve`; ready when `<root>/home/service.json` reports `runs_settled: true`; bearer token in owner-only `<root>/home/service.token` (`agent:src/cadrumo_agent/lifecycle/discovery.py:106-134`, `:315-328`; `agent:src/cadrumo_agent/control/state_layout.py:249-326`). Stores must already match the build (`agent:src/cadrumo_agent/control/hosted_stores.py:16-36`).
- Hosted lanes are `anthropic` (direct API, in process) and `claude` (Claude Code via ACP) only (`agent:src/cadrumo_agent/providers/lane_admission.py:614-616`).

### cadrumo-agent: conversations, metadata, archive, delete

- Conversation list: missing. A conversation is a directory under `<root>/home/workspaces/` (`agent:src/cadrumo_agent/control/state_layout.py:198-201`). `GET /v1/runs?workspace_root=` filters live runs only, returning `run_id` and `status` (implemented, tested by `agent:src/cadrumo_agent/api/tests/test_active_run_discovery_live.py:126`). With `state=all` the workspace is validated and then dropped (`agent:src/cadrumo_agent/api/routes/_gateway_read_endpoints.py:133-149`; `agent:src/cadrumo_agent/database/thread_repository.py:364-408`). A run's workspace is readable only from `GET /v1/runs/{id}/history` (`agent:src/cadrumo_agent/api/schemas/gateway.py:482`).
- Metadata: per run only. `title` is caller-supplied, up to 200 characters, with no generation (`agent:src/cadrumo_agent/api/schemas/gateway.py:172`); `created_at`, `updated_at` per run (`agent:src/cadrumo_agent/database/models.py:198-202`). No conversation title, last activity, message count or preview.
- Archive: run-level only, terminal runs only (`agent:src/cadrumo_agent/control/thread_service.py:598-631`). No restore: `ARCHIVED` has no outgoing transition (`agent:src/cadrumo_agent/thread/transitions.py:80`). The route docstring says a repeat is 409; the code returns 200 (`thread_service.py:612-614`). No conversation-level archive.
- Continue a settled run: implemented via `POST /v1/runs` with `continues_run_id`, up to 20 prior messages carried (`agent:src/cadrumo_agent/api/routes/_gateway_run_start.py:308-333`, `:536-557`). Follow-up into a live run: `POST /v1/runs/{id}/messages` (`agent:src/cadrumo_agent/api/routes/_gateway_action_endpoints.py:678-709`). Stream: SSE with resume by `Last-Event-ID` (`agent:src/cadrumo_agent/api/routes/_gateway_read_endpoints.py:285-347`).
- Conversation delete: gated (404 without a hosted root, `agent:src/cadrumo_agent/api/routes/_gateway_conversation_endpoints.py:60-61`). Removes runs, the workspace including attachments, and Claude Code transcript folders; resumable via `home/state/conversation-removals.json` (`agent:src/cadrumo_agent/control/conversation_deletion.py:10-27`, `:274-359`). Service-level tests use real stores but always pass `ending=None`, so ending a live run is untested (`agent:src/cadrumo_agent/control/tests/test_conversation_deletion.py:191-537`).
- One live run per root in hosted mode (`agent:src/cadrumo_agent/control/thread_service.py:306-312`).

### cadrumo-agent: attachments, files at rest, catalog

- Register, list, remove: implemented, untested (route tests cannot pass, no direct test of `agent:src/cadrumo_agent/control/attachments.py:184-276`). Files live at `<workspace>/attachments/<name>`, placed by the host; 50 MiB default bound (`agent:src/cadrumo_agent/domain_config.py:254-262`); no type restriction; links and multiply-linked files refused; SHA-256 returned by register only and stored nowhere; list capped at 1000 names.
- ZIP: missing; no archive extraction anywhere in `agent:src`.
- Encryption at rest: missing. Attachments, both SQLite stores and transcripts are plaintext; the `claude` lane also leaves Claude Code transcripts in the provider home (`agent:src/cadrumo_agent/control/conversation_deletion.py:274-346`).
- Model reading: the direct lane reads UTF-8 text only, up to 256 KiB (`agent:src/cadrumo_agent/providers/_direct_tools.py:121-136`); no lane has an image or PDF proof (`agent:src/cadrumo_agent/providers/lane_admission.py:486-499`).
- Provider catalog: implemented. Per model `efforts[]` and `default_effort`; providers that are not installed or signed in stay listed with `selectable: false` and reasons; built by live prompt-free CLI handshakes, cached 300 s per workspace (`agent:src/cadrumo_agent/api/schemas/provider_catalog.py:83-203`; `agent:src/cadrumo_agent/providers/provider_catalog_service.py:53-195`). No passing route test checks the shape against a real provider.
- Client authentication: bearer token on every `/v1` route (`agent:src/cadrumo_agent/api/auth.py:28-37`). No code takes or stores a Cadrumo credential.

### Cadrumo: desktop shell, sign-in, MCP admission

- The shell holds no runtime connection (`.vault/adr/2026-10-04-desktop-shell-adr.md:82`, restated `:127`). It drives sign-in by short-lived fixed CLI children (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:1`, `:43-80`), verifies `aeat` against the package manifest digest (`mod.rs:183-216`), and builds every child from `ChildConfiguration` with a cleared, projected environment (`native/application/src/child.rs:9-15`, `:89-96`; `native/platform/src/storage.rs:587-602`).
- Sign-in state reaches the webview through a 2 s `config sign-in-status` poll (`native/desktop/src-tauri/src/shell/sign_in/observation.rs:60-81`), carrying `state`, `active_profile` label and `runtimeAvailable` (`native/desktop/src-tauri/src/shell/sign_in/wire.rs:34-41`). Pushed session events reach only runtime connections (`src/cadrumo/entrypoints/runtime/session_events.py:14-41`), so not the shell.
- The webview's CSP `connect-src` admits only Tauri IPC (`native/desktop/src-tauri/tauri.conf.json.in:19`).
- `cadrumo-agent` is not a packaged entrypoint; the package scripts are `aeat`, `cadrumo-mcp`, `cadrumo-runtime` (`pyproject.toml:140-142`).
- `cadrumo-mcp` admits itself: configured key, else resume of the stored receipt over its own verified connection, else attendance (`src/cadrumo_harness/mcp/runtime_adapter.py:119-132`, `:293-321`; `src/cadrumo/adapters/local_runtime/frontend_client.py:305-312`). It binds the selected profile at first resume and refuses a later mismatch (`src/cadrumo_harness/mcp/runtime_admission.py:77-97`). It loses its session on sign-out, expiry or lock by itself (`runtime_adapter.py:232-245`).
- Open work this depends on: `2026-10-10-mcp-parity-plan` `P02.S18` (assistant messages as activity; receipt-sealing-key location), `P10.S68` (desktop sign-in view on lock and pushed events), `P10.S70` (live proof of MCP inside the signed-in profile); `2026-10-12-attended-live-sign-in-plan` `S04`, `S05`.
- No record in this vault decides that the desktop hosts cadrumo-agent; the agent column is a placeholder (`native/desktop/frontend/src/App.tsx:2069-2100`).

### Cadrumo: document custody

- `AttachmentStore` holds content-addressed, encrypted bytes and manifests (`src/cadrumo/adapters/persistence/storage/attachment.py:164-184`, `:282-303`, `:418-451`; namespaces `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:809-827`). Manifests link transactions and invoices, not conversations; the model forbids extra fields and a new typed link needs a manifest schema version (`src/cadrumo/domain/attachments/models.py:134-150`; `attachment.py:363-366`). `AttachmentSource` has no agent channel (`src/cadrumo/domain/attachments/enums.py:50-68`). There is no per-attachment delete (`attachment.py:282-510`).
- Ingest from a path: `ledger.evidence.add` (pdf, xml, images; no size ceiling; Cadrumo computes the digest) (`src/cadrumo/application/ledger/evidence_add_operation.py:55-84`; `src/cadrumo/application/ledger/evidence.py:343-363`, `:529-560`); `ledger.import` (csv, tsv, xlsx, xls, ofx, qfx; 128 files; 64 MiB guard; bytes not kept in custody) (`src/cadrumo/application/ledger/import_operation.py:56-60`; `src/cadrumo/adapters/inbound/financial/providers/base.py:71-75`). No intake for docx or md; no general archive extraction.
- Decrypted bytes exist only in memory on every read path (`src/cadrumo/application/ledger/evidence_input.py:1-14`, `:104-109`; `src/cadrumo/adapters/outbound/llm/models.py:51-74`). Accepted rulings forbid temp files and the agent file-path route "even under consent" (`.vault/adr/2026-06-10-llm-evidence-classification-adr.md:123-145`) and plaintext financial documents outside custody (`.vault/adr/2026-06-10-ledger-evidence-enforcement-adr.md:167`).
- Bytes never enter MCP results; only registered output projections do (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:165`). Existing precedent: evidence drafts expose field values and a transcription digest and length, not raw text (`src/cadrumo/application/ledger/invoice_evidence_operation_dtos.py:259`, `:295-298`).
- Consent is per invocation and bound to one digest, never persisted (`src/cadrumo/adapters/outbound/llm/consent.py:19-25`, `:137-256`); dispatches are recorded in an unpruned consent ledger (`src/cadrumo/adapters/persistence/llm/consent_ledger.py:94-158`). The owner's "one standing consent" ruling exists only in cadrumo-agent's vault, quoted at `.vault/reference/2026-10-10-mcp-parity-file-exchange-reference.md:27`, and conflicts with `.vault/adr/2026-06-10-llm-evidence-classification-adr.md:140-142`.
- The plaintext exchange folder ADR was rejected for gating admission, not for being plaintext (`.vault/adr/2026-10-10-mcp-parity-file-exchange-adr.md:25`); the owner's ruling for a plaintext folder beside encrypted storage is quoted at `.vault/reference/2026-10-10-mcp-parity-file-exchange-reference.md:26`.

### cadrumo-agent: what hosted mode persists (second audit, 2026-10-12)

The hosted root is called R.

**Plaintext with private content:**
- `R/home/state/cadrumo-agent.db` and its WAL. It holds messages, context preamble, seeded earlier turns, run definitions, titles and failure text. It also holds the SSE replay log: model text, reasoning and truncated tool output. Locators: `agent:src/cadrumo_agent/ipc/schemas.py:162-187`, `agent:src/cadrumo_agent/control/accepted_input.py:35-46`, `agent:src/cadrumo_agent/streaming/run_event_writer.py:137`, `agent:src/cadrumo_agent/database/models.py:578-618`.
- `R/home/state/checkpoints.db` and its WAL. It holds the full LangGraph state, with plaintext metadata (`agent:src/cadrumo_agent/database/checkpoints.py:291-325`).
- `R/home/runtime/gateway.log` and `worker.log`, plus a never-removed `worker-autospawn-<port>.stderr.log`. These are not proven content-free (`agent:src/cadrumo_agent/utils/logging.py:264-287`, `:527-541`; `agent:src/cadrumo_agent/control/_worker_health.py:245-247`).
- Workspaces and their attachments. Anything the model or Cadrumo's CLI writes there is plaintext.
- `R/tmp` and `R/scratch`, emptied only at the next start (`agent:src/cadrumo_agent/control/hosted_start.py:150-219`).
- The Claude Code lane's `R/providers/claude/projects/` transcripts (`persistSession` is never set), its sign-in credential and state, and its cache directory outside R (`agent:src/cadrumo_agent/providers/_hosted_provider_home.py:18-31`; `agent:src/cadrumo_agent/providers/_acp_session.py:122-126`; `agent:src/cadrumo_agent/workspace/environment.py:151-176`).

**Credentials in files:** `R/home/service.token` and `R/home/credentials/<worker IPC secret>` (`agent:src/cadrumo_agent/lifecycle/discovery.py:455-460`; `agent:src/cadrumo_agent/desktop/credentials.py:169-197`).

**Where a key can enter.** Every process opens a store before anything else.
- **Gateway:** `agent:src/cadrumo_agent/api/app.py:917` (store check), then `:384` and `:853`.
- **Worker:** `agent:src/cadrumo_agent/worker/app.py:611` and `:262`.
- **CLI steps:** `agent:src/cadrumo_agent/cli/service.py:397-476`.
- **Store openers** are listed at `agent:src/cadrumo_agent/database/session.py:374`, `:476`, `:663`; `agent:src/cadrumo_agent/database/migrations/env.py:225`; `agent:src/cadrumo_agent/database/checkpoints.py:300`; `agent:src/cadrumo_agent/database/checkpoint_schema.py:249`, `:336`; `agent:src/cadrumo_agent/database/compatibility.py:163`, `:227`, `:420`; `agent:src/cadrumo_agent/desktop/migration.py:195`, `:244`, `:284`.

**Encryption seams:**
- aiosqlite accepts a connector callable.
- SQLAlchemy accepts `async_creator`.
- `AsyncSqliteSaver` accepts a connection.

So one SQLCipher connector can serve every store. Two risks: SQLCipher's error classes are not `sqlite3`'s, and Windows cp313 wheels must be confirmed.

**Version surface:** `cadrumo-agent version --json` gives `api_version` and `package_version` (`agent:src/cadrumo_agent/cli/main.py:226-245`). There is no hosting-contract version and no store-format version.

**Packaging:**
- `requires-python >=3.13`.
- One hard dependency conflict: cadrumo-agent requires `anthropic>=1.13,<2`, while Cadrumo's extra declares `>=0.74.1,<1` and locks `0.125.0`.
- The Node adapter is needed only by the Claude Code lane.
- There is no `__main__` module.
- The Node install root is undefined inside site-packages (`agent:src/cadrumo_agent/control/infra_config.py:36-42`).

**Accepted cadrumo-agent records the 2026-10-12 owner rulings reverse:**
- conversation-data-posture: plaintext history, and it rejects in-agent encryption with a Cadrumo key, lines 50-51 and 62-65;
- profile-data-root: a plaintext directory beside encrypted storage, lines 75-77;
- shipping-and-versioning, together with project-boundary: ships beside Cadrumo, never inside it;
- hosting-contract: fixed environment names and `service.token`.

### Cadrumo: storage boundary, keys, launcher, packaging, consent (second audit, 2026-10-12)

**Storage root:**
- The root is `CADRUMO_LOCAL_STORAGE_ROOT`, with `CADRUMO_STORAGE_ROOT` also accepted in a source checkout; otherwise the per-user default (`src/cadrumo/core/storage_environment.py:162-194`, `:417-424`, `:454-489`).
- The selected profile comes from the in-process override or the `active-profile` pointer (`src/cadrumo/core/bucket_pointer.py:291-299`).

**Capsule and keystore:**
- The capsule is `<root>/buckets/<profile-uuid>/` (`src/cadrumo/core/storage_taxonomy_locations.py:1040`).
- The deletion inventory reads every capsule file by path and content, except the database, its write-ahead sidecars and the lock (`src/cadrumo/adapters/persistence/storage/custody/_inventory.py:28-101`). It is bounded at 2048 entries and 512 MiB (`:25-26`).
- Deletion refuses on any change since preflight (`src/cadrumo/application/user_profile/custody_service.py:665-686`).
- The keystore is a per-profile sibling at `<root>/keystore/<id>/` (`src/cadrumo/core/storage_taxonomy.py:91-102`). It is the precedent for a sibling per-profile root, with a deletion step modelled on session acceleration (`src/cadrumo/application/user_profile/login_session.py:285-307`).

**Storage categories and lifecycle:**
- New categories are declared at `src/cadrumo/core/storage_taxonomy.py:207-451`.
- The deletion journal states and owners are at `src/cadrumo/application/user_profile/custody_transactions.py:91-106` and `:438-450`.
- Reset reuses profile deletion (`src/cadrumo/application/config_reset.py:1032-1038`).
- Reclaim never touches bucket-scoped unbounded state (`src/cadrumo/application/storage_management/service.py:70-85`).

**Keys:**
- The DEK is wrapped by envelopes (`src/cadrumo/adapters/persistence/storage/custody/capsule.py:1130-1192`).
- The acceleration receipt splits a keychain key from a wrapped DEK, and no DEK reaches a frontend (`src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py:9-49`).
- The precedent for a random per-profile key minted on first use is `review-package-signing-key` (SECRET, PROFILE_LOCAL, PROCESS_LOCAL) (`src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:975-984`; `src/cadrumo/adapters/persistence/profile/review_package_signing.py:49-97`). SECRET declares that a finite TTL is required (`src/cadrumo/core/classification/policies.py:34-37`).
- Secret frames reach clients only on the enrollment and installation doors (`src/cadrumo/entrypoints/runtime/enrollment_connections.py:271-274`; `src/cadrumo/entrypoints/runtime/installation_door.py:289-302`). No registered operation returns key material.

**Resume:**
- Non-interactive CLI resume is refused by a client-side gate (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:119-126`; `src/cadrumo/entrypoints/cli/config/secure_input.py:443-457`), as `.vault/adr/2026-10-04-application-sign-in-adr.md:91-94` states.
- MCP has its own exception (`:92`).
- `resume_receipt()` is a public client method (`src/cadrumo/adapters/local_runtime/frontend_client.py:305-330`).
- Frontends are `cli`, `mcp`, `tui` (`src/cadrumo/application/operations/registry.py:190-199`). Person acts are refused on MCP (`src/cadrumo/application/operations/person_acts.py:27-72`).

**Session events:**
- Every client subscribes to session retirement (`src/cadrumo/adapters/local_runtime/frontend_client.py:159-176`, `:281-284`).
- The MCP adapter re-resumes once before giving up (`src/cadrumo_harness/mcp/runtime_adapter.py:243-256`).

**Child environment:** `child_environment` clears unlisted `CADRUMO_` names (`src/cadrumo/core/storage_environment.py:646-650`, `:682-685`).

**Packaging:**
- Wheels come from `uv.lock`, one PyPI registry package each (`dev/packaging/runtime_wheel_selection.py:193-206`, `:277-298`), and are installed with hashes (`dev/packaging/native/provision.py:59-102`).
- The manifest carries `distributions` and per-file digests (`dev/packaging/native/assemble.py:323-351`).
- Entrypoints are Cadrumo's own console scripts, resolved exactly once (`dev/packaging/native/layout.py:66-69`; `native/interpreter/bootstrap.py:149-160`).
- Version-refusal precedent: `cadrumo-runtime --expected-version`, exit 69 (`src/cadrumo/entrypoints/runtime/main.py:219`).
- Optional-component precedent: the `user_docs` manifest statement, mapped to Bundled, NotBundled or Undeclared (`dev/packaging/native/assemble.py:345-346`; `native/application/src/package.rs:29-37`; `native/desktop/src-tauri/src/environment.rs:103-109`).

**Consent surfaces:**
- The CLI asks for off-host consent through flags (`src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py:257-289`).
- The TUI has no off-host consent screen (`src/cadrumo/entrypoints/tui/runtime_evidence.py:208-225`).
- Observation needing live verification: `ledger.evidence.extract` takes `acknowledge_off_host` as a request field, is not a person act, and is open on the full MCP surface (`src/cadrumo/application/ledger/invoice_evidence_extract_operation.py:62-81`; `src/cadrumo/application/operations/person_acts.py:70-72`; `src/cadrumo/application/operations/mcp_surfaces.py:136-143`). An MCP agent may therefore supply its own acknowledgement. This was reported to the mcp-parity owner on 2026-10-12. They confirmed it on a real runtime and fixed it in `3f15f3bdcc`: an off-host extraction requested over MCP now gets the person-act refusal. The consent record still stores the fixed surface string.

### Feasibility (third audit, 2026-10-12)

Only the documentation was read: no SQLCipher code was executed, and `PRAGMA key` with `?mode=ro` and wrong-key behaviour are untested.

**Encryption library.**
- `sqlcipher3` 0.6.3 (2026-10-04, zlib/libpng) is the only maintained SQLCipher DB-API package with self-contained cp313 wheels for win_amd64, manylinux_2_28 x86_64 and aarch64, and macOS arm64. It bundles SQLCipher 4.12.0 on SQLite 3.51.1, with OpenSSL 3.6.0 statically linked.
- The wheels meet the release floors (`dev/packaging/runtime_wheelhouse_contract.py:53-75`).
- SQLCipher Community requires attribution in the application's notices.

**Fitting it to the agent's stack.**
- It works with aiosqlite through a connector callable, with `AsyncSqliteSaver(conn)`, and with SQLAlchemy `async_creator`.
- Its exception classes derive from `Exception`, not from `sqlite3`'s. SQLAlchemy's aiosqlite dialect therefore leaves them unwrapped, so the agent's `sqlite3` catch sites need a dialect shim or dual catches.
- The key must be applied inside the connector, before the agent sets `journal_mode=WAL` (`agent:src/cadrumo_agent/database/session.py:94-100`).
- WAL and journals are encrypted, but other temp files are not, so temp storage must stay in memory.

**Fallback without a native dependency.** Use application-level AES-GCM through `cryptography` (already locked by both projects), with a LangGraph `EncryptedSerializer` and column TypeDecorators. This leaves ids, statuses, timestamps, workspace paths, nicknames and the LangGraph checkpoint `metadata` column in plaintext. `EncryptedSerializer` also silently accepts unencrypted rows (`langgraph/checkpoint/serde/encrypted.py:28-30`).

**anthropic 1.x.** The upgrade removes `temperature` from `messages.create`. Cadrumo always sends it (`src/cadrumo/adapters/outbound/llm/providers/anthropic.py:146`, `:176-177`, `:282`; the default is `0.0` at `src/cadrumo/core/config_runtime_fields.py:188-189`), so every Anthropic call would raise `TypeError` until the adapter routes it through `extra_body` or declares it unsupported. Two more effects:
- The type gates on `anthropic.py:282` are likely to fail.
- `role_fitness.py:168` timeout detection walks `httpx` types, which become `httpx2`.

anthropic is not in Cadrumo's bundled base closure today. Bundling cadrumo-agent adds it together with `jiter`, `docstring-parser`, `distro` and `sniffio`.

**Publishing cadrumo-agent.** It has no releases on PyPI (`https://pypi.org/pypi/cadrumo-agent/json` returns 404). Publishing a pure-Python wheel there needs no change to the wheel selector, which requires a single hashed PyPI registry wheel (`dev/packaging/runtime_wheel_selection.py:193-243`). A path source would be excluded from the constraint export, and would conflict with the product-cohort check (`dev/packaging/native/product.py:101-105`).

**Dependency overlap.** Apart from anthropic, the only resolver conflict is `websockets`:
- Cadrumo pins 17.2 for the dev-only `sphinx-autobuild` (`pyproject.toml:578`).
- `langgraph-sdk` requires `<17`.
- 16.1.1 satisfies both.

Six runtime packages resolve at Cadrumo's older pins, which the agent has not been tested against: pydantic, pydantic-core, sqlalchemy, opentelemetry-api, pycparser and rpds-py. All of the agent's runtime-only native packages have cp313 wheels for the four targets.

### cadrumo-agent: the live-run path (fourth audit, 2026-10-13)

Read from `git show HEAD:` at cadrumo-agent 4c5f6f5. The checkout at that commit carries about 250 uncommitted source files, among them a 12-tool `cadrumo` relay entry in place of 18. That work is in progress, not this audit's evidence.

**Startable modes.**
- Without a hosted root, `serve` starts (`agent:src/cadrumo_agent/cli/main.py:249`; `agent:src/cadrumo_agent/api/app.py:908`). Stores migrate at start (`app.py:384-385`), and the proof policy is `warn` (`agent:src/cadrumo_agent/control/infra_config.py:338`). Implemented.
- With `CADRUMO_AGENT_HOSTED_ROOT`, the relay is mandatory (`agent:src/cadrumo_agent/providers/lane_registry.py:237`). Plugins, the only other switch, are refused beside a root (`infra_config.py:1041-1061`). The proof sets are still empty (`agent:src/cadrumo_agent/providers/lane_admission.py:481-484`), so a start exits 78 (`app.py:157`, `:194`). Gated. Verified by `agent:src/cadrumo_agent/control/tests/test_hosted_start_refusals.py:319`.
- `desktop-serve` refuses every run with 503 without a verified OS isolation backend (`agent:src/cadrumo_agent/control/provider_execution.py:21-35`). Gated.
- The hosted parts without a root (strict limits, no provider sign-in) are reachable only through a test-tree plugin (`agent:src/cadrumo_agent/testing/lanes/hosted_parts.py:51-76`). Missing for a host.

**Relay.** HEAD launches `cadrumo-mcp --surface full` by bare name and declares 18 tools (`agent:src/cadrumo_agent/providers/_harness_mcp_registry.py:386-408`). A served-tool mismatch fails only that run's mount (`agent:src/cadrumo_agent/providers/_direct_mcp.py:299-315`), and run start answers 422 (`agent:src/cadrumo_agent/api/routes/_gateway_run_start.py:237-272`).

**Credentials and token.**
- The Anthropic key is read only from the environment variable `CADRUMO_AGENT_ANTHROPIC_API_KEY` (`agent:src/cadrumo_agent/control/env_registry.py:80-81`, `:144`; `agent:src/cadrumo_agent/providers/provider_readiness.py:136-154`). Implemented.
- The gateway bearer is `CADRUMO_AGENT_GATEWAY_TOKEN`, or a per-process token published in an owner-only handoff file (`app.py:951`; `agent:src/cadrumo_agent/lifecycle/discovery.py:402-457`). Implemented.
- No stdin frame exists for either. Missing.

**Models.** The anthropic catalog lists models through `client.models.list(limit=100)` (`agent:src/cadrumo_agent/providers/anthropic_catalog.py:235`). No Claude id is hardcoded. Implemented.

**One turn over HTTP.** All routes are Implemented.
- `POST /v1/runs` takes `run_id`, `message` and `agent.provider` and `agent.workspace_root`, plus optional `model`, `effort`, `title` and `continues_run_id` (`agent:src/cadrumo_agent/api/schemas/gateway.py:150-174`).
- `GET /v1/runs/{id}/stream` serves SSE frames: `message_chunk`, `thought_chunk`, `tool_call_start`, `tool_call_update`, `error`, `stream_snapshot`, `thread_terminal`, `permission_request`, `heartbeat` and `progress_dropped` (`agent:src/cadrumo_agent/streaming/sse_frames.py:316-403`). `Last-Event-ID: -` replays.
- `POST /v1/runs/{id}/messages` needs an `Idempotency-Key`. `POST /v1/runs/{id}/cancel` cancels.
- Readiness is `GET /health`, or `runs_settled` in `service.json`.

**Workspace.** The host creates `<workspaces>/<id>` itself. Admission refuses a directory that does not exist (`agent:src/cadrumo_agent/control/workspace.py:65-86`). No code maps a conversation id to a workspace.

**Live evidence.** `agent:src/cadrumo_agent/service_tests/test_hosted_direct_lane_live.py` proves a direct-lane turn under the hosted layout, through the test plugin, with the relay off and the `warn` policy. It does not prove a gateway given a hosted root or any Cadrumo tool call. It runs with `-m service` and needs `CADRUMO_AGENT_ANTHROPIC_API_KEY`. Verified for the lane only.

### Cadrumo: what a live lane can reuse (2026-10-13)

- `dev/agent_eval/live/isolated_host.py:1-12` starts a verified copy of the packaged bundle on a fresh storage root. It passes the person's secrets only on the protected stdin channel, and gives every packaged process an allow-listed environment (`:41-64`).
- `dev/agent_eval/live/access.py:212-249` has the person request and approve an agent key. Only the key's reference comes back. This admission path exists for a Cadrumo MCP server and never involves the password.
- The `read_only_local` MCP surface serves 10 tools: every tool except the two review tools, restricted to operations that change no record and contact no other host (`src/cadrumo/application/operations/mcp_surfaces.py:103-150`).
- Cadrumo reads its Anthropic key only from the environment variable behind `cadrumo_llm_anthropic_api_key` (`src/cadrumo/core/config_llm_fields.py:52-55`). The desktop clears unlisted `CADRUMO_` variables from every child it starts (`src/cadrumo/core/storage_environment.py:646-650`). No stored provider credential exists.
- The desktop frontend's browser host serves nothing (`native/desktop/frontend/src/shell/host.ts:1-7`), so the development display on port 15370 can never run the agent. Only the Tauri host can.
- `native/desktop/frontend/src/shell/agentSession.ts` declares the webview's session contract, served by no host.
