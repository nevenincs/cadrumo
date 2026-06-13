---
tags:
  - '#research'
  - '#google-oauth'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - "[[2026-05-06-google-oauth-audit]]"
  - "[[2026-04-21-google-auth-ux-adr]]"
  - "[[2026-04-12-google-fixtures-adr]]"
  - "[[2026-05-06-secure-persistence-enforcement-adr]]"
  - "[[2026-04-12-data-storage-adr]]"
  - "[[2026-04-17-attachment-service-adr]]"
---

# `google-oauth` research: codebase reality + fresh-state OAuth design

## Brief

The project's previous Google integration was anchored on `gcloud auth application-default login` plus a service-account fallback. The user-facing assertion has been: *"Google services are interactive review gates which allow in-flight tax-return amendments, reviews, and states exported for human review and editing, with changes pulled back in programmatically."* This research has two parts: (a) verify that assertion against the codebase as it stands today (post-teardown commit `ab952f74`), and (b) ground the forthcoming ADR in current 2026 OAuth, library, scope, storage, and UX practice.

The codebase audit was reinforced by six parallel sub-agents (one Sonnet plus five Sonnet/Haiku follow-ups) reading every file in the filing, review, aggregation, attachments, transactions, financial-inbound, workflow, sede, observability, and CLI subsystems, plus exhaustive token greps and git-history forensics on every deleted Google module. The convergent verdict is recorded in §1; the external 2026 research that grounds the ADR is in §2-§7; the open questions and decision points are in §8.

## §1 — Codebase reality (audit-confirmed)

### 1.1 The user's assertion vs. what exists

| User-asserted use case | Verdict | Evidence |
|---|---|---|
| Export tax return / draft / declaration to Sheets for operator review | REFUTED | Zero code path in `application/filing/`, `application/review/`, `application/aggregation/`, `application/verification/`, `domain/filing/`, `domain/submission/` or `entrypoints/cli/_declaration*` writes to Sheets, Docs, or Drive. The only "export" is `_export.py::export_draft` writing fichero-BOE bytes to a local `Path`. The "review" lifecycle (`approve_draft`/`unapprove_draft`/`refresh_review_status` in `application/filing/_review.py`) is purely local, with `approved_by` as an operator-name string. |
| Pull operator-edited changes back from Sheets/Docs | REFUTED | No reader exists. `reconciliation/_reconcile.py` accepts a `Justificante \| None` parsed from a local PDF; the caller is responsible for fetching it. No remote reconcile path. |
| Drive import for filings / PDFs / transaction documents / bank statements | REFUTED | Every inbound provider in `adapters/inbound/` is path-only (`ingest(path: Path)`). `RawProvenance.source_path: Path` is a hard constraint preventing URI provenance. The only bytes-ready entry point is `parse_declaracion_bytes(pdf_bytes: bytes)` in `adapters/inbound/declaracion/_parser.py` — declaración parsing alone could plug a Drive fetcher; everything else needs a materialise-to-tempfile shim. |
| Ledger export to Sheets | REFUTED + EXPLICITLY DEFERRED | No code in `domain/calculations/`, `application/aggregation/`, or `entrypoints/cli/_ledger*` produces Sheets output. The 2026-04-12 `data-storage` ADR states verbatim: *"Export to Sheets/Drive: explicitly deferred. The research rejected Sheets as a primary backend; a read-only export adapter is a later issue."* |
| `aeat drive fetch` for AEAT certificate | DEAD-END | The deleted `aeat-cert-fetch` justfile recipe used Drive only as a convenient operator file store for PKCS#12 certs. Today certs come from a local `AEAT_CERTIFICATE_PATH`. No replacement Drive flow planned. |
| Scratch resource flow (`AEAT_SCRATCH_FOLDER_ID/SHEET_ID/DOC_ID`) | DEAD-END | The three scratch IDs were consumed only by live-test skip guards (`requires_scratch_*` in deleted `_live.py`), Sheets/Drive/Docs API smoke tests (deleted `_test_*_live.py`), and the deleted `aeat doctor` health check. They were never wired into filing, review, aggregation, or any domain logic. |
| Test fixtures (`AEAT_GOOGLE_TEST_FIXTURE_*`) | DEAD-END | Three fixture-ID config fields existed for a `tests/live/test_google_fixtures_smoke.py` that was never landed; the `scripts/` directory that would have provisioned them never existed on disk. |
| Inbox / justificante / filing-history pushed/pulled from Google | REFUTED | `domain/justificante/`, `application/workflow/`, `adapters/outbound/aeat/sede/_notifications.py` have zero Google references. `RemoteNotification.mode: Literal["read"] = "read"` is a structural read-only marker. There is no inbox CLI surface at all (no `aeat inbox` command group). |
| MCP integration purpose | DEAD-END | The deleted `aeat.entrypoints.mcp.launch_google_workspace` was a process-replacement shim that loaded `Settings`, validated auth, mapped env vars, and `os.execvpe`'d `uvx workspace-mcp --tool-tier core`. MCP was the **primary** consumer of the Google stack — it gave Claude/Gemini coding agents a Workspace MCP server for ad-hoc dev sessions. None of those tool calls were wired into AEAT domain logic. |
| `AttachmentSource.GOOGLE_DRIVE` enum | STUBBED | Defined in `domain/attachments/_enums.py:56`. Never assigned anywhere. Same for `AttachmentSource.GMAIL`, `AttachmentSource.URL`, and `AttachmentKind.DRIVE_DOCUMENT` (line 33) — three of the five `AttachmentSource` values plus one `AttachmentKind` value are taxonomic placeholders with zero consumers. |

### 1.2 What the original Google stack actually did (per its own deleted docstrings)

Reconstructed from `git show <commit>~1:<path>` for every deleted module. Verbatim docstring evidence:

- **`adapters/outbound/google/__init__.py`** (deleted in `ab952f74`): *"Google authentication and GCP service builders for AEAT automation. Supports two operator-facing Google auth paths: (1) Desktop OAuth local-dev — interactive Desktop OAuth client plus a repo-local OAuth token cache for CLI/bootstrap work on a workstation. (2) Service-account automation — headless use via `GOOGLE_APPLICATION_CREDENTIALS` for automation and server contexts."*
- **`entrypoints/cli/bootstrap.py`** (deleted in `785c66ad`): *"`aeat bootstrap` — provision scratch resources after authentication. Picks up where `just gcloud-auth` and `just gsuite-enable-apis` leave off: validates ADC + scope set + API enablement, then idempotently creates the `aeat-scratch` Drive folder, Sheet, and Doc (if they do not already exist), and writes their IDs back into `env/.env`."*
- **`entrypoints/cli/drive.py`** (deleted in `785c66ad`): *"`aeat drive` sub-app — Drive v3 helpers via the discovery client. Every command builds the Drive service lazily so importing this module does not pay the discovery round-trip cost. Output goes through rich where it benefits from a table or colour, and through stdout for raw file content (so `aeat drive cat ID > file` works)."*
- **`entrypoints/cli/oauth.py`** (deleted in `785c66ad`): *"`aeat oauth-client` Typer sub-app — guided OAuth Desktop client provisioning. There is no public Google API or `gcloud` command that creates an OAuth 2.0 client ID for a project; the developer has to click through the Cloud Console. This command prints the exact link, parses the resulting JSON download, and populates the workstation's `env/.env` so bootstrap/operation can proceed."*

**Synthesised actual primary purpose:**

1. Developer-workstation bootstrap (OAuth client provisioning + ADC acquisition + API enablement) so a fresh clone could reach Google Workspace at all.
2. Scratch-resource provisioning (an `aeat-scratch` folder + Sheet + Doc) used by Drive/Sheets/Docs API live smoke tests to prove API connectivity.
3. Drive download for AEAT PKCS#12 certificate files (via `aeat drive fetch`) — operator convenience, not a domain integration.
4. MCP shim so coding agents (Claude, Gemini) could browse/edit Drive, Sheets, and Docs interactively during dev sessions.
5. A planned but never implemented "real-PDF-fixture corpus" Drive workflow (Kent's private real filings → scrub → corpus) named in `.vault/adr/2026-04-21-real-pdf-fixture-corpus-adr.md`.
6. Speculative-only "export-target Sheet" / "divergence sink Sheet" mentions in `.vault/research/2026-04-12-google-fixtures-research.md` (issues #10/#11) — explicitly deferred.

**The user's "interactive review gates" framing is not supported by any module docstring, ADR, research doc, or code path.** What review lives in this codebase is the local `FilingDraft.approved_by` / `approved_at` fingerprint plus the `ReviewQueue` CLI surface. No Google round-trip exists or was ever specified.

### 1.3 Stale, dead-end, and uncertain entries discovered

**Stale (still on disk, references deleted concepts):**

| Location | What it claims |
|---|---|
| `src/aeat/domain/attachments/_enums.py:33` | `AttachmentKind.DRIVE_DOCUMENT` enum value, no consumer |
| `src/aeat/domain/attachments/_enums.py:49` | `AttachmentSource.GOOGLE_DRIVE` enum value + docstring "A document fetched from Google Drive" |
| `src/aeat/domain/attachments/_enums.py:55` | `AttachmentSource.GMAIL` enum value, no Gmail adapter exists |
| `src/aeat/domain/attachments/_enums.py` (line varies) | `AttachmentSource.URL` enum value, no URL fetcher exists |
| `src/aeat/domain/attachments/__init__.py:4-9` | Module docstring lists "Gmail messages, Drive documents" as supported attachment kinds |
| `src/aeat/domain/attachments/_models.py:86-87` | `source_reference` field docstring: "e.g. a Gmail message id, a Drive file id, a local path" |
| `src/aeat/core/env_io.py:3-4` | Module docstring: *"The bootstrap workflow persists resource identifiers (Drive folder, Sheets ID, Docs ID) back into `env/.env` after authenticated API calls create them"* — code is generic env-file reader/writer with zero cloud-specific behaviour |
| `src/aeat/core/errors/__init__.py:63-70` | `FixtureProvisioningError` docstring: *"Raised when Google Workspace test-fixture provisioning fails. Thrown by the provisioning and teardown scripts whenever a Drive / Sheets / Docs call cannot satisfy the catalogued intent."* — class is unraised anywhere |
| `src/aeat/core/observability/_store.py` (docstring) | Cloud-sync advisory: *"Callers that sync `var/runs/` to cloud storage must understand that every one of these fields is in scope"* — no cloud-sync code exists; warning is forward-looking |
| `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py:32` | Lists `adapters/outbound/google` in `_SENSITIVE_SURFACES` (scaffold path resolves; entry was sized for the full 957-line adapter) |
| `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py:37` | Lists `entrypoints/cli/oauth.py` in `_SENSITIVE_SURFACES` — file no longer exists, scanner silently skips |
| `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py:3-4` | Docstring example references `google.oauth2.service_account.Credentials.from_service_account_file` — no longer a runtime dependency |
| `src/aeat/core/config.py:431` | Setting `aeat_llm_gemini_api_key` description "Google Gemini API key" — keep (Gemini LLM is in scope, separate from Workspace) |
| `tests/README.md:143` | References `just google-fixtures-provision` recipe — recipe was removed |

**Dead-end (deleted in teardown, no consumer survived):**

- All deleted CLI files (`oauth.py`, `drive.py`, `docs.py`, `cloud.py`, `bootstrap.py`, `doctor.py`, `_drive_helpers.py`, `_docs_helpers.py`, `_sheets_helpers.py`)
- Deleted MCP shim (`entrypoints/mcp/launch_google_workspace.py`)
- All deleted `_test_*_live.py` files for Drive/Sheets/Docs/Cloud round-trips
- Deleted `auth/__init__.py` (40 KB) and `auth/_render.py`
- Pre-excision content of `adapters/outbound/google/__init__.py` (17.8 KB) and `_paths.py` (20.4 KB)
- Pre-excision content of `_live.py` (Google service factories — `requires_live_enabled` retained)
- Justfile recipes: `gcloud-install/auth`, `gsuite-bootstrap[-sa]`, `gsuite-enable-apis[-billing]`, `gsuite-doctor`, `gsuite-oauth-client`, `google-fixtures-provision/teardown`, `aeat-cert-fetch`

**Uncertain / not-yet-implemented (vault doc describes, no code):**

| Vault doc | What it describes |
|---|---|
| `.vault/research/2026-04-12-google-fixtures-research.md` | Issues #10 (export-target Sheet) and #11 (divergence sink Sheet) — both explicitly deferred |
| `.vault/adr/2026-04-12-data-storage-adr.md` | Sheets export deferred verbatim (line 79) |
| `.vault/adr/2026-04-12-attachment-service-adr.md` (#76) | *"The attachment service deliberately does not solve ingestion (Gmail/Drive pulls)... those remain downstream work in #80, #86, and #89."* |
| `.vault/adr/2026-04-21-real-pdf-fixture-corpus-adr.md` | Kent-only Drive→scrub→corpus dev workflow (developer corpus building, not operator-facing) |
| `.vault/research/2026-05-06-live-parity-oracle-backend-research.md` | Mentions Sheets/Docs in passing as possible visualisation surfaces |

### 1.4 Blast radius for the rebuild

If we re-introduce a Google OAuth provider with Drive read + Sheets read/write, the rebuild touches at most:

- `src/aeat/adapters/outbound/google/` — replace scaffold with real `__init__.py`, `_oauth.py`, `_storage.py`, `_services.py` (4 files, ~600 lines)
- `src/aeat/core/config.py` — re-introduce `google_*` Settings fields (smaller set than before — see §6)
- `env/.env.example` — re-introduce `GOOGLE_OAUTH_CLIENT_*` keys
- `pyproject.toml` — add `google-auth`, `google-auth-oauthlib`, `google-api-python-client`
- `tests/import_contract/test_adr_layout_import_smoke.py` — already asserts the package + 2 symbols; just expand `CANONICAL_PUBLIC_SYMBOLS` if more are exported
- New test files under `src/aeat/adapters/outbound/google/` (colocated unit tests + an opt-in live test)

NOT touched (zero blast radius):

- Filing / review / aggregation / verification (no integration today, none planned for v1)
- Domain models (no schema changes)
- Workflow engine (no new step)
- Inbox / justificante / observability (no new sink)

This is intentionally a thin slice. The "interactive review gate" use case is not part of this rebuild.

## §2 — Authentication method (2026)

### 2.1 Recommended OAuth flow for desktop CLI

Loopback IP redirect via `InstalledAppFlow.run_local_server(port=0)` is the canonical 2026 path. PKCE is on by default. The out-of-band (OOB) flow was fully deprecated 2023-01-31 and is blocked for all client types globally. Loopback was deprecated for mobile/Chrome-app clients in 2022 but **explicitly retained for the "Desktop app" OAuth client type**.

Sources: [OAuth 2.0 for iOS & Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app), [OOB Migration Guide](https://developers.google.com/identity/protocols/oauth2/resources/oob-migration), [Loopback IP Migration Guide](https://developers.google.com/identity/protocols/oauth2/resources/loopback-migration).

Newer alternatives evaluated and rejected for our use case:

- **Device authorization grant (RFC 8628)** — designed for input-limited devices (TVs); no ergonomic advantage on a workstation with a browser.
- **Sign in with Google JavaScript SDK** — browser-only, not for CLI.
- **Chrome Identity API** — Chrome extension only.

### 2.2 Cloud Console client type

Use **Desktop app**. Web application requires a publicly-accessible redirect URI; TVs and limited input devices is the device-grant flow.

### 2.3 Verification policy

| Status | Constraint | Implication for us |
|---|---|---|
| Testing (unverified) | 100 test users; access tokens expire 7 days from consent; refresh tokens valid 7 days for the testing project | Adequate for a personal-tool deployment with one operator (the autónomo himself) |
| In Production (verified) | No user cap; refresh tokens have no expiry except 6-month-unused / 100-token-account-cap / password-change / explicit revoke | Required only if we publish the OAuth client multi-tenant; not needed for a single-operator deployment where the operator brings their own Cloud Console project |

The clean v1 recommendation is **operator-supplied OAuth client** (operator creates the Desktop client in their own Cloud Console project): no verification required, no Google review, full sensitive-scope coverage, testing-mode for life. Cost: operator must do the one-time Cloud Console setup.

## §3 — Library versions (latest stable as of 2026-05-06)

| Library | Latest | Released | Notes |
|---|---|---|---|
| `google-auth` | 2.50.0 | 2026-04-30 | Successor to the 2.49.x baseline previously pinned. Minor API changes only. |
| `google-auth-oauthlib` | 1.3.1 | 2026-03-30 | API stable since 1.0. `InstalledAppFlow` unchanged. |
| `google-api-python-client` | 2.195.0 | 2026-04-30 | Weekly releases; pin major.minor in `pyproject.toml`. |
| `google-auth-httplib2` | 0.3.1 | 2026-03-30 | **DEPRECATED** — repo archived 2026-03. Drop. Use `requests`-based transport from `google-auth` directly. |

Async alternatives surveyed: `gcloud-aio`, `aiogoogle`. No first-party async SDK from Google. For a synchronous desktop CLI, the standard sync libraries above are the right choice; we have no async hot-path requirement.

Sources: [google-auth · PyPI](https://pypi.org/project/google-auth/), [google-auth-oauthlib · PyPI](https://pypi.org/project/google-auth-oauthlib/), [google-api-python-client · PyPI](https://pypi.org/project/google-api-python-client/), [google-auth-httplib2 · PyPI](https://pypi.org/project/google-auth-httplib2/).

**Recommended dependency block:**

```toml
"google-auth>=2.50.0",
"google-auth-oauthlib>=1.3.1",
"google-api-python-client>=2.195.0",
```

`gspread` (previously pinned at 6.2.1) is dropped — the bus-factor-1 maintenance status and the fact that we use `google-api-python-client` directly for Sheets makes it redundant. `google-cloud-functions/run/storage` are dropped — no production caller existed for any of them. Net runtime dep delta: 8 dropped → 3 added.

## §4 — Desktop app per-profile setup prerequisites

### 4.1 Operator one-time Cloud Console steps

1. Create a Google Cloud Project (or reuse an existing personal project).
2. Enable APIs: `drive.googleapis.com` and `sheets.googleapis.com`.
3. Configure OAuth consent screen: External user type, Testing publishing status, the operator's own email as the sole test user, app name and support email set.
4. Create OAuth 2.0 Credentials of type "Desktop application". Download the JSON.
5. Run `aeat google register --client-json /path/to/downloaded.json --profile <profile_id>` to import into our SecureObjectRepository.

### 4.2 Required APIs

- Drive API (`drive.googleapis.com`) — file fetch + (eventually) folder listing.
- Sheets API (`sheets.googleapis.com`) — only enabled when the Sheets-export feature is opted in.

Docs API (`docs.googleapis.com`) is NOT required for v1 since the codebase audit refutes the existence of any Docs round-trip flow. Defer until a concrete consumer exists.

### 4.3 OAuth consent screen

Field-by-field requirements: app name (operator-chosen), support email (operator's email), developer contact email (same), authorised redirect URIs (`http://127.0.0.1:0/` is fine — `run_local_server(port=0)` picks an ephemeral port and Google accepts loopback ranges), scopes (the minimal set declared by the app — see §5), test users (operator's own Google account email).

Source: [Manage OAuth Clients](https://support.google.com/cloud/answer/15549257?hl=en), [When is verification not needed](https://support.google.com/cloud/answer/13464323?hl=en).

### 4.4 Programmatic client provisioning

There is no public Google API or `gcloud` command that creates an OAuth 2.0 client ID. The Cloud Console click-through is mandatory for the operator. Our CLI `aeat google register` accepts the downloaded JSON and stores it; we cannot automate the creation step.

### 4.5 Free-tier quotas (verified 2026)

| API | Per-project per-minute | Per-user per-project per-minute | Daily |
|---|---|---|---|
| Drive | 1,000,000 quota units | 325,000 quota units | 400,000,000 unit free tier; 750 GB upload/day; 5 TB max single file |
| Sheets | 300 read req + 300 write req | 60 read req + 60 write req | No daily limit specified |

Per-unit costs: `files.list` 100, `files.get_media` 200, `files.update` 50, `spreadsheets.values.append` counts as 1 write req. For a single autónomo (≈100-500 transactions/year, ≈50-200 invoices, ≈12-24 bank statements), free tier is comfortable — calls/month estimated at ~60 reads + ~20 writes, against a 60/min/user cap.

Sources: [Drive API Limits](https://developers.google.com/workspace/drive/api/guides/limits), [Sheets API Limits](https://developers.google.com/workspace/sheets/api/limits).

## §5 — Authorisation scopes

### 5.1 Scope catalogue (verified 2026)

| Scope | Sensitivity | Verification needed |
|---|---|---|
| `https://www.googleapis.com/auth/drive` (full) | Restricted | Yes (security assessment) |
| `https://www.googleapis.com/auth/drive.readonly` | Restricted | Yes |
| `https://www.googleapis.com/auth/drive.file` (per-file) | Non-sensitive | No |
| `https://www.googleapis.com/auth/drive.metadata.readonly` | Non-sensitive | No |
| `https://www.googleapis.com/auth/spreadsheets` | Sensitive | Yes (3-5 business days) |
| `https://www.googleapis.com/auth/spreadsheets.readonly` | Sensitive | Yes |
| `https://www.googleapis.com/auth/documents` | Sensitive | Yes |

Sources: [OAuth 2.0 Scopes](https://developers.google.com/identity/protocols/oauth2/scopes), [Choose Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [Choose Sheets scopes](https://developers.google.com/workspace/sheets/api/scopes).

### 5.2 Recommended minimal v1 set

```python
SCOPES_REQUIRED = [
    "https://www.googleapis.com/auth/drive.file",   # non-sensitive; covers Sheets-files we create too
]
SCOPES_OPTIONAL = {
    "sheets_export": "https://www.googleapis.com/auth/spreadsheets",  # sensitive; opt-in
}
```

Rationale:

- `drive.file` is non-sensitive: zero verification required even outside testing mode. Grants read+write to files the app created or the operator explicitly opened via the Drive picker. Sufficient to read operator-uploaded PDFs/CSVs/OFX provided the operator picks them through the app.
- `spreadsheets` is sensitive but works in Testing mode for up to 100 users without verification; an operator-supplied OAuth client never leaves Testing mode in practice. Opt-in only when the Sheets export feature is enabled.
- Avoid `drive` (full): restricted scope, security assessment, blast radius too large.
- Avoid `drive.readonly`: also restricted; `drive.file` covers everything we actually need for v1 and the operator has explicit per-file control.
- Defer `documents`: no consumer in the codebase, no use case proven yet.

### 5.3 Scope opt-in / opt-out model

Google does not allow per-scope revocation; revocation is all-or-nothing per OAuth grant. Incremental authorisation via `include_granted_scopes='true'` lets the app request additional scopes after initial grant, surfacing a second consent screen only for the new scope.

For our CLI: declare required scopes at module level, additional scopes per feature flag. CLI `aeat google login --enable-sheets-export` requests `spreadsheets` alongside `drive.file`. Without the flag, only `drive.file` is requested, and any code path that needs Sheets access either degrades gracefully or refuses with a clear "rerun `aeat google login --enable-sheets-export`" message.

There is no fine-grained per-scope per-resource control at the OAuth layer; folder-level Drive grants do not exist. Scope is the only granularity.

## §6 — Token storage + multi-profile sessions

### 6.1 Token TTLs (Google policy 2026)

- Access token: 1 hour TTL.
- Refresh token in Testing project: invalidated after 7 days from consent.
- Refresh token in Production project: no expiry except 6-month-unused / 100-token-account-cap / Gmail-scope password change / explicit revoke.
- Revocation surfaces as HTTP 400 `error: "invalid_grant"`; Google stops sending `error_description` 12 hours after revocation, so detection must happen at the next API call.

Sources: [Google OAuth Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices), [RFC 9700 OAuth Security BCP](https://datatracker.ietf.org/doc/rfc9700/), [OWASP OAuth 2.0 Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html).

### 6.2 Mandated storage locations

The repo's secure-persistence substrate landed in `53b20235` and is the right home:

- `SecureObjectRepository` (SQL-backed, envelope-encrypted, classification-aware) under `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- `SecretStore` namespace `aeat.outbound.google.oauth_tokens` for refresh tokens (SECRET classification).
- `SecretStore` namespace `aeat.outbound.google.oauth_clients` for the operator's downloaded Desktop OAuth client JSON (also SECRET).
- Master key in OS keychain via `MasterKeyProvider` AUTO mode; encrypted-file fallback (Argon2id-wrapped AES-256-GCM) for headless / CI; UNSECURED mode refused when the active profile carries a real NIF/NIE/CIF.

XDG/OS conventions for the legacy file fallback (only relevant if `keyring` is unusable): Linux `$XDG_DATA_HOME/aeat/`, macOS `~/Library/Application Support/aeat/`, Windows `%LOCALAPPDATA%\aeat\`. The current `aeat_token_dir` setting defaults to `<project>/.tokens/` — fine for development but the production path resolution should respect XDG when a profile is loaded outside the project tree.

Three obsolete `.gitignore` entries (`gcp-oauth.keys.json`, `.gdrive-server-credentials.json`, `.mcp-google-sheets-token.json`) are already removed in `ab952f74`. The new design has no plaintext-on-disk secrets to ignore.

### 6.3 Multi-profile session management

The repo already supports operator profiles (`AEAT_PROFILE` env var, `application/setup/_models.py::SetupAnswers`). For multi-profile OAuth:

```text
SecureObjectRepository natural keys:
  aeat:google:profile:<profile_id>:oauth-token       # SECRET — refresh token
  aeat:google:profile:<profile_id>:oauth-client      # SECRET — Desktop client JSON
  aeat:google:profile:<profile_id>:oauth-metadata    # AUDIT — granted scopes, account email, issued_at
```

Each profile carries its own refresh token, its own granted-scopes set, and its own Google-account email. Profile switching is via `AEAT_PROFILE=<id>` env var (already supported). Lookup is HMAC-indexed (the natural key never appears in the database). Comparable patterns: `gcloud config configurations`, GitHub CLI's `gh auth switch`, AWS CLI named profiles, kubectl contexts.

### 6.4 Refresh strategy

Lazy refresh with a 5-minute clock-skew buffer: before each API call, `if expiry - now < 5min: refresh()`. `google.auth.transport.requests.Request().refresh(creds)` mutates `creds` in place; re-persist the refresh token on each call (Google occasionally rotates). On `invalid_grant`, mark profile as "re-auth required" and prompt at next interactive use; never auto-retry.

### 6.5 Integration with secure-persistence ADR

The `2026-05-06-secure-persistence-enforcement-adr` already lists `aeat.outbound.google.oauth_tokens` and `aeat.outbound.google.oauth_clients` namespaces in the secure-storage policy. Aligning with it is a no-op — just emit those namespace records when storing.

## §7 — Drive / Sheets API patterns for the use cases that actually exist

### 7.1 Drive ingest patterns (in scope only when feature lands)

Per the codebase audit (§1), no Drive ingest exists today. If we later add it, the canonical patterns:

- Binary download: `files().get_media(fileId=...)` → `MediaIoBaseDownload` with 50 MB chunks for streaming.
- Listing: `files().list(q="'<folder_id>' in parents and mimeType='application/pdf' and trashed=false", fields="files(id,name,mimeType,md5Checksum,modifiedTime,size)")`.
- Integrity: verify `md5Checksum` (sha256Hash absent on Google-native files).
- Polling for changes: `changes().list(pageToken=...)` — webhooks not viable for desktop CLI.

The path-only inbound providers (`CsvProvider`, `XlsxProvider`, `OfxProvider`, `PdfN26Provider`, justificante parser) all need a tempfile materialisation step before they can consume Drive content. The declaración parser already exposes `parse_declaracion_bytes(pdf_bytes)` — the only inbound surface that's Drive-ready without refactor.

The minimum-friction adapter shape is a generic `DriveFileFetcher` that downloads to a `tempfile.NamedTemporaryFile` and yields a `Path` — this works for every existing provider without modifying any of them. `RawProvenance.source_path: Path` would record the temp path; if we want to preserve Drive origin, we'd need to add a `source_uri: str | None` field. That's a future concern — not in v1 scope.

### 7.2 Sheets export patterns (in scope only when feature lands)

Per the codebase audit (§1), no Sheets export exists today and the data-storage ADR explicitly defers it. If/when we add it:

- Create: `spreadsheets().create()` (the OAuth identity becomes owner).
- Append: `spreadsheets().values().append(range='Ledger!A1:N1', valueInputOption='USER_ENTERED', insertDataOption='INSERT_ROWS', body={'values': rows})`. Range must include the header row for the API to detect the table bounds; using a header-less range appends below the last formula cell.
- Format: `spreadsheets().batchUpdate()` with `updateSheetProperties` + `repeatCell` requests.
- Read-back: `values().get(range=..., valueRenderOption='UNFORMATTED_VALUE')` for computation; `FORMATTED_VALUE` for display.
- Versioning: no per-write revisionId on Sheets; use Drive `files().get(fields='version')` to detect operator-side edits.

Quota verdict: 60 read + 60 write requests per minute per user is comfortable for our scale.

### 7.3 Docs round-trip (out of scope for v1)

The codebase audit refutes any Docs round-trip use case. The Docs API is not in v1. If a future "interactive review gate" is genuinely wanted:

- Docs returns a JSON tree from `documents().get(includeTabsContent=True)`; text lives in nested `paragraph.elements[].textRun.content`.
- `batchUpdate(replaceAllText, insertText, deleteContentRange)` for writes.
- Suggestions can be READ via `suggestionsViewMode='SUGGESTIONS_INLINE'` but cannot be programmatically accepted/rejected; the operator must click in the Docs UI.
- Comments API does NOT exist for Docs.
- Round-trip "operator edits the doc, app pulls back" requires manual operator approval in UI; cannot be fully programmatic.

This is enough information to ADR a future Docs feature; not enough to commit to building one.

### 7.4 Permissions and sharing

- `drive.file` scope auto-covers files the app created (the operator never has to share manually). For files the operator already owns, the operator must pick them through the Drive picker for the scope to apply.
- Folder-level OAuth grants do not exist. If an "ingest folder X" UX is wanted, the operator manually shares the folder with the app's OAuth identity and the app lists children with `'<folder-id>' in parents`.
- `drive.permissions.create` to share a Sheet back with the operator's email (if the app created it under its own identity, which it won't with Desktop OAuth — the OAuth identity IS the operator).

## §8 — Open questions answered + decision points for the ADR

### Open question 1: What is the proper authentication method and role implementation in 2026?

Loopback IP redirect via `InstalledAppFlow.run_local_server(port=0)` with PKCE on. Cloud Console client type "Desktop app". Operator-supplied OAuth client (operator brings their own Cloud Console project) avoids verification entirely. Roles are not a Google-OAuth concept; the OAuth grant is per-account, and access control is per-scope (all-or-nothing within a scope). Fine-grained authorisation must live in our application logic.

### Open question 2: What are the latest versions of the Google authentication library?

`google-auth==2.50.0`, `google-auth-oauthlib==1.3.1`, `google-api-python-client==2.195.0`. Drop `google-auth-httplib2` (archived). Drop `gspread` (bus-factor 1; we use `google-api-python-client` directly). Drop `google-cloud-functions/run/storage` (no caller existed).

### Open question 3: What are the prerequisites to set up a desktop application for a user to authenticate per profile?

Operator one-time: create Cloud Console project, enable Drive + Sheets APIs, configure consent screen, create Desktop OAuth client, download JSON. App side: `aeat google register --client-json <path> --profile <id>` stores the JSON in SecureObjectRepository under `aeat:google:profile:<id>:oauth-client`. First `aeat google login --profile <id>` runs the loopback flow and stores the refresh token under `aeat:google:profile:<id>:oauth-token`.

### Open question 4: Best practices for storing tokens given the secure-storage mandate?

Refresh token → `SecureObjectRepository` SECRET classification, namespaced per profile, encrypted via the substrate's envelope-wrapped DEKs with KEK in OS keychain (AUTO backend) or Argon2id-wrapped passphrase (file backend). Access token → in-memory only. Operator-supplied OAuth client JSON also SECRET. Refuse storage when `aeat_secret_store_backend=unsecured` and the active profile has a real NIF/NIE/CIF.

### Open question 5: What are the locations that are usually mandated?

OS-keychain for the master key. SQL-backed `SecureObjectRepository` for the encrypted records. The current `aeat_token_dir` default `<project>/.tokens/` is acceptable for a project-scoped install; for a system-installed deployment, prefer XDG-conformant paths (`$XDG_DATA_HOME/aeat/` on Linux, `~/Library/Application Support/aeat/` on macOS, `%LOCALAPPDATA%\aeat\` on Windows). Decision: leave the default at the project tree, document XDG override.

### Open question 6: How are token sessions managed?

Lazy refresh with 5-minute clock-skew buffer. Re-persist refresh token after every `Request().refresh(creds)` call (Google occasionally rotates). On `invalid_grant`, mark profile re-auth-required and prompt at next interactive use. Never auto-retry. Detect 7-day-testing-project policy at first refresh and warn the operator.

### Open question 7: Multi-profile session and authentication management?

One refresh token per profile, namespaced via SecureObjectRepository natural keys (`aeat:google:profile:<id>:oauth-token`). Profile selected via `AEAT_PROFILE` env var (already wired in the repo). Per-profile metadata records granted scopes, Google-account email, and issued-at timestamp. Comparable patterns surveyed: gcloud configurations, gh auth switch, AWS CLI profiles, kubectl contexts.

### Open question 8: Scope opt-in / opt-out UX?

Required scope (`drive.file`) requested at first login. Optional scopes (`spreadsheets`) opted in via flag (`--enable-sheets-export`). Incremental authorisation via `include_granted_scopes='true'` so subsequent logins only show the new scope's consent screen. Google does not allow per-scope revocation; only per-grant revocation via the operator's Google Account settings. App must degrade gracefully when an optional scope is denied: detect via `creds.scopes`, refuse the dependent feature with a clear "rerun `aeat google login --enable-sheets-export`" message.

### Decision points the ADR must close before Phase 2

1. **CLI shape**: `aeat google {register,login,status,logout}` (top-level google sub-app) **vs** retain `aeat auth` umbrella with `--provider google` sub-routing (alignment with the existing AEAT-side auth provider registry in `entrypoints/cli/auth/_registry.py`).
2. **Adapter library shape**: keep `googleapiclient.discovery.build()` based service builders **vs** rewrite to pure `httpx` against Drive v3 / Sheets v4 REST endpoints.
3. **Excision strategy for the scaffold**: replace the NotImplementedError stubs in `adapters/outbound/google/` with the real implementation in one PR **vs** build alongside under `adapters/outbound/google/_oauth/` and cut over later.
4. **Scope set v1**: `drive.file` only (refuses Sheets export until v2) **vs** `drive.file` + `spreadsheets` (full v1 surface, requires `--enable-sheets-export` opt-in flag).
5. **Stale enum cleanup**: remove `AttachmentSource.GMAIL`, `AttachmentSource.URL`, `AttachmentKind.DRIVE_DOCUMENT` immediately as part of the same ADR **vs** keep as taxonomy placeholders pending future ADRs (#76, #80, #86, #89 attachment-ingestion line of work).
6. **`aeat drive fetch` replacement**: do nothing (operators place certificates locally; current state) **vs** add a one-shot `aeat google fetch <drive-file-id>` operator convenience.
7. **MCP shim disposition**: the deleted `launch_google_workspace.py` was the primary consumer of the old stack. Decide explicitly: leave deleted (current state — coding agents lose Workspace MCP) **vs** rebuild on top of the new OAuth provider once it lands.
8. **Operator-supplied vs published OAuth client**: operator brings their own Cloud Console project (zero verification, single-tenant, our default) **vs** we maintain a published verified OAuth client (requires Google review, scales to many operators).

Each decision must be answered explicitly in the ADR. The teardown audit (`[[2026-05-06-google-oauth-audit]]`) records the pre-excision baseline; this research records the codebase reality and the 2026 grounding for the design.
