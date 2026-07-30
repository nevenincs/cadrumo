<!-- GENERATED FILE - DO NOT EDIT.
Regenerate with: uv run --no-sync python -m dev.docs.env_reference
Source of truth: cadrumo.core.config.Settings -->

# Environment overrides

This page covers every environment variable the application reads, generated
from the live settings model. Environment overrides are advanced deployment
and development configuration: every user workflow works without them through
prompts, command flags, and `aeat config` commands. Set an override only when
you administer a deployment and know why the default does not fit.

An annotated template with the same variables lives at `env/.env.example` in
the repository; the runtime also reads them from `env/.env`. A value set in
the process environment wins over the `.env` file.

| Variable | Type | Default | What it controls |
| --- | --- | --- | --- |
| `AEAT_AUTHORITATIVE_LANGUAGE_AEAT_TERMS` | str | `es` | Authoritative language for domain terminology (modelos, registry definitions, references). |
| `AEAT_BASE_URL` | str | (derived) | AEAT sede electrónica base URL |
| `AEAT_CLAVE_PERMANENTE_SEDE_ACCESS_URL_TEMPLATE` | str | (derived) | URL template for AEAT's auth-method selector page used by the Cl@ve Permanente login flow. `{target}` is replaced with the URL-encoded target path. The default template is sourced from the external constants registry. |
| `AEAT_CLAVE_SEDE_ACCESS_URL_TEMPLATE` | str | (derived) | URL template for AEAT's auth-method selector page. `{target}` is replaced with the URL-encoded target path. The default template is sourced from the external constants registry. |
| `AEAT_MANUALS_ROOT` | Path | (derived) | Root directory for the structured AEAT Manual práctico corpus |
| `AEAT_NORMATIVES_ROOT` | Path | (derived) | Root directory for the bundled legal normatives corpus |
| `AEAT_SEDE_EXPEDIENTES_PATH` | str | (derived) | AEAT Sede path for 'Mis expedientes' — the default post-auth target used by Cl@ve Móvil login and the expedientes reader. |
| `AEAT_STATUS_DETAIL_URL_TEMPLATE` | str | (derived) | URL path template for an expediente detail page. Must contain '{expediente_id}'. Override only when AEAT changes the corresponding route. |
| `AEAT_STATUS_NOTIFICACIONES_PATH` | str | (derived) | URL path for the 'Mis notificaciones' listing page. Joined against aeat_base_url. Override only when AEAT changes the corresponding route. |
| `CADRUMO_ALLOW_UNENCRYPTED` | str | empty | Hostile-named opt-out gate for the unsecured backend. Must be set to the literal '1' (env var: CADRUMO_ALLOW_UNENCRYPTED=1) to use cadrumo_secret_store_backend=unsecured. The unsecured backend is intended for testing / educational / throwaway scenarios only and provides ZERO confidentiality. The substrate refuses to load an operator profile that carries a real NIF/NIE/CIF while running in unsecured mode. |
| `CADRUMO_ATTACHMENTS_DIR` | Path | (derived) | Root directory for the attachment byte and manifest store |
| `CADRUMO_AUDIT_DIR` | Path | (derived) | Directory for the governed audit sink (redacted, classification-aware) |
| `CADRUMO_AUTH_CERTIFICATE_LOCK_TTL_S` | int | `180` | Acquisition lock TTL (seconds) for certificate-backed AEAT auth flows |
| `CADRUMO_AUTH_CLAVE_MOVIL_LOCK_BUFFER_S` | int | `90` | Headroom (seconds) added to ``cadrumo_clave_movil_timeout_ms`` for the acquisition lock TTL |
| `CADRUMO_AUTH_PROVIDER` | AuthProviderKind | unset | Default auth provider for `aeat config auth status` / `test` when --provider is omitted. When None, the CLI auto-selects the first configured provider from the canonical registry order. |
| `CADRUMO_AUTH_TIMEOUT_MS` | int | `30000` | Playwright navigation timeout for protected AEAT authentication in milliseconds |
| `CADRUMO_AUTHORITATIVE_LANGUAGE_PROJECT_DOCS` | str | `en` | Authoritative language for internal code and documentation |
| `CADRUMO_BLOB_STORE_DIR` | Path | (derived) | Directory containing the encrypted blob store (content-addressed, classification-aware) |
| `CADRUMO_BROWSER_BUSCAR_SETTLE_MS` | int | `3000` | Settle delay (ms) after the AEAT 'Buscar' button before reading the results table |
| `CADRUMO_BROWSER_CHANNEL` | str | `chrome` | Playwright browser channel to use (e.g., 'chrome', 'chromium', 'msedge') |
| `CADRUMO_BROWSER_CLOSE_TIMEOUT_MS` | int | `5000` | Best-effort timeout (ms) for Playwright browser context/session cleanup during AEAT live auth and read flows. Cleanup must not leave a command hanging after the primary operation has already failed or timed out. |
| `CADRUMO_BROWSER_FORM_INTERACTION_TIMEOUT_MS` | int | `10000` | Timeout for individual form interactions (fill/click/wait) in milliseconds |
| `CADRUMO_BROWSER_HEADLESS` | bool | `true` | Run browser in headless mode |
| `CADRUMO_BROWSER_LOCALE` | str | `es-ES` | Default browser locale passed to Playwright context (BCP-47 tag) |
| `CADRUMO_BROWSER_NAVIGATION_TIMEOUT_MS` | int | `30000` | Default Playwright navigation timeout (milliseconds) for AEAT sede pages |
| `CADRUMO_BROWSER_SELECTOR_PROBE_TIMEOUT_MS` | int | `2500` | Selector visibility probe timeout (ms) used by GROI/NIF-IVA check stages |
| `CADRUMO_BROWSER_TIMEZONE` | str | `Europe/Madrid` | Default IANA timezone string passed to Playwright context |
| `CADRUMO_BROWSER_VER_CLICK_TIMEOUT_MS` | int | `15000` | Timeout (ms) for the AEAT declarations 'Ver' button click and navigation |
| `CADRUMO_BROWSER_VIEWPORT_HEIGHT` | int | `900` | Default Playwright viewport height (px) for AEAT sede sessions |
| `CADRUMO_BROWSER_VIEWPORT_WIDTH` | int | `1366` | Default Playwright viewport width (px) for AEAT sede sessions |
| `CADRUMO_BUCKET_DEFAULT_IDLE_LOCK_MINUTES` | int | `15` | Fallback idle-lock window (minutes) when a bucket manifest omits the value |
| `CADRUMO_BUCKET_DEFAULT_SESSION_ABSOLUTE_MINUTES` | int | `240` | Fallback absolute session-lifetime cap (minutes) when a bucket manifest omits session_absolute_minutes; fixed at login and never refreshed, so a touched-forever session still seals at this cap (default 4 h, 12 h hard ceiling) |
| `CADRUMO_BUCKET_LOCK_POLL_INTERVAL_S` | float | `0.1` | Polling interval (seconds) for bucket lockfile acquisition retries |
| `CADRUMO_CALC_SHEETS_RECALC_DELAY_S` | float | `2.0` | Delay (seconds) waiting for Google Sheets server-side recalculation between parity polls |
| `CADRUMO_CERT_CRITICAL_DAYS` | int | `14` | Critical threshold (days) for the certificate pre-expiry gate: certificates with <= this many days remaining are CRITICAL and must be renewed before authenticated AEAT work continues |
| `CADRUMO_CERT_WARN_DAYS` | int | `60` | Warning threshold (days) for the certificate pre-expiry gate: certificates with <= this many days remaining are surfaced as WARN |
| `CADRUMO_CERTIFICATE_FRIENDLY_NAME` | str | unset | Optional human-readable label for the certificate |
| `CADRUMO_CERTIFICATE_PASSWORD_SECRET` | SecretStr | (secret) | PKCS#12 passphrase (env only, never logged or persisted) |
| `CADRUMO_CERTIFICATE_PATH` | Path | unset | Filesystem path to the operator's PKCS#12 (.p12/.pfx) bundle |
| `CADRUMO_CLAVE_MOVIL_DNI_FECHA` | str | unset | DNI validity / expiry date (YYYY-MM-DD) used by the non-QR Cl@ve Móvil fallback form. Applies when the configured identity is a DNI. |
| `CADRUMO_CLAVE_MOVIL_DNI_NIE` | SecretStr | (secret) | Taxpayer DNI/NIE for `aeat config auth configure --provider clave_movil`. Used to stamp the persisted session with the operator's identity and to pre-fill the non-QR fallback form. AEAT-regulated personal identifier under Spanish tax law; typed as SecretStr to prevent leakage through repr / model_dump / ValidationError. |
| `CADRUMO_CLAVE_MOVIL_NIE_SOPORTE` | SecretStr | (secret) | NIE support number (número de soporte) used by the non-QR Cl@ve Móvil fallback form. Applies when the configured identity is a NIE. AEAT-regulated personal identifier; typed as SecretStr to prevent leakage. |
| `CADRUMO_CLAVE_MOVIL_TIMEOUT_MS` | int | `120000` | Maximum time (milliseconds) the Cl@ve Móvil provider waits for AEAT browser-side authentication completion before aborting. Production runs must fail fast enough for an operator to retry deliberately rather than leaving a pending request dangling. |
| `CADRUMO_CLAVE_PERMANENTE_DNI_NIE` | SecretStr | (secret) | Taxpayer DNI/NIE for `aeat config auth configure --provider clave_permanente`. Used as the Cl@ve IdP login username and to stamp the persisted session with the operator's identity. AEAT-regulated personal identifier under Spanish tax law; typed as SecretStr to prevent leakage through repr / model_dump / ValidationError. |
| `CADRUMO_CLAVE_PERMANENTE_PASSWORD` | SecretStr | (secret) | Cl@ve Permanente password for the DNI/NIE + password login form. Same treatment as the certificate passphrase: env var only, never stored in a committed env file, never logged. |
| `CADRUMO_CLAVE_PERMANENTE_TIMEOUT_MS` | int | `60000` | Maximum time (milliseconds) the Cl@ve Permanente provider waits for the AEAT/Cl@ve IdP login form round-trip to complete before aborting. Routine Cl@ve Permanente login is headless-automatable (DNI/NIE + password, no SMS), so this window is shorter than the human-in-the-loop Cl@ve Móvil timeout. |
| `CADRUMO_CLAVE_PREFER_NON_QR` | bool | `false` | When true, the Cl@ve Móvil provider uses the non-QR fallback (DNI/NIE + contraste) rather than the QR code. This still requires operator-mediated completion in Cl@ve. |
| `CADRUMO_CLI_REVEAL_IDENTIFIERS` | bool | `false` | Reveal raw profile and bucket identifiers in CLI success output instead of the paste-safe ``<profile-id>`` / ``<bucket-id>`` placeholders. Default off keeps the centralised-output-redaction policy (profile/bucket UUIDs are redacted so diagnostics are safe to paste into shared notes). A multi-client gestor who must disambiguate which bucket a command addressed sets ``CADRUMO_CLI_REVEAL_IDENTIFIERS=1`` to opt out. This only un-redacts the opaque profile/bucket UUIDs; NIF/NIE/CIF tax identities, bearer tokens, URLs, and secure-object keys stay redacted unconditionally. |
| `CADRUMO_CORPUS_TEXT_CACHE_DIR` | Path | (derived) | Directory for the registry corpus source-text validation cache (normalised text keyed by content fingerprint) |
| `CADRUMO_DATABASE_URL` | str | empty | SQLAlchemy URL for the primary persistence backend. When empty, the model validator resolves the URL through the active-profile precedence chain to ``sqlite:///<cadrumo_local_storage_root>/buckets/<bucket-id>/db/cadrumo.db``; with no active profile it derives a root-level fallback at ``sqlite:///<cadrumo_local_storage_root>/cadrumo.db`` so the URL is never empty when the storage root is set. Tests that need a deterministic location supply this field explicitly; production reads the computed value. |
| `CADRUMO_DEADLINE_DUE_SOON_DAYS` | int | `14` | Days before an obligation's closes_on date that flag ObligationStatus.DUE_SOON in the deadline engine |
| `CADRUMO_DEV_TEST_DATABASE_PASSWORD` | SecretStr | (secret) | Development/test-only password used by secure-storage subprocess tests. |
| `CADRUMO_DRAFT_FAIL_ON_WARNING` | bool | `false` | If true, build_draft raises FilingValidationError when any WARNING- or ERROR-severity finding is produced |
| `CADRUMO_DRAFTS_DIR` | Path | (derived) | Directory where filing drafts are written as JSON files |
| `CADRUMO_EVIDENCE_CLOUD_UPLOAD_PERMITTED` | bool | `false` | Whether this deployment permits transmitting evidence to a cloud model at all. Default off: evidence reading is on-host only. When True, a per-invocation operator consent acknowledgement is still required for each cloud read. |
| `CADRUMO_EVIDENCE_GESTOR_MODE` | bool | `false` | Gestor/professional deployment flag. When True, cloud evidence upload is categorically refused regardless of cadrumo_evidence_cloud_upload_permitted or per-invocation consent. |
| `CADRUMO_FALLBACK_LANGUAGES` | str | `es,en` | Comma-separated fallback chain consulted when the target language is missing. |
| `CADRUMO_FILE_LOCK_RETRY_BACKOFF_S` | float | `0.05` | Sleep interval (seconds) between non-blocking file-lock acquire attempts |
| `CADRUMO_FILE_LOCK_TIMEOUT_S` | float | `30.0` | Default exclusive file-lock acquisition timeout (seconds) |
| `CADRUMO_FILING_HISTORY_ARCHIVE_HTML` | bool | `false` | If true, archive fetched detail-page HTML under <cadrumo_filing_history_dir>/pages/ |
| `CADRUMO_FILING_HISTORY_CACHE_TTL_S` | int | `900` | TTL in seconds for per-expediente filing-history cache entries (default 15 min) |
| `CADRUMO_FILING_HISTORY_DIR` | Path | (derived) | Directory where the persisted ModeloHistory JSON file lives |
| `CADRUMO_FINANCIAL_TXS_DIR` | Path | (derived) | Directory where the transaction catalogue JSON file is stored |
| `CADRUMO_FORCE_COLOR` | bool | `false` | Force ANSI colour output even when stdout is not a TTY. Operators set this when piping Cadrumo output through a terminal renderer (less -R, gh actions, etc.). Defaults to False; the should_use_color() helper consults this and the standard NO_COLOR convention through Settings rather than reading os.environ directly. |
| `CADRUMO_FX_RATE_LOOKUP_TIMEOUT_S` | int | `15` | Timeout (seconds) for one ECB Data Portal euro reference-rate lookup. A ledger import resolves one lookup per distinct currency/date, so this budget bounds a single observation query rather than the whole import. |
| `CADRUMO_GOOGLE_DRIVE_ROOT_FOLDER_ID` | str | unset | Drive folder ID under which `cadrumo-vault/` is created and used. Required when cadrumo_storage_provider_kind=google_drive. Operator obtains this from the Cloud Console / Drive web UI; the app creates `cadrumo-vault/` lazily on first probe. |
| `CADRUMO_GOOGLE_DRIVE_VAULT_FOLDER_NAME` | str | `cadrumo-vault` | Folder name created under the Google Drive root for the Cadrumo vault |
| `CADRUMO_GOOGLE_OAUTH_ACCESS_REFRESH_BUFFER_S` | int | `300` | Clock-skew buffer (seconds) before nominal expiry when refreshing Google access tokens |
| `CADRUMO_INBOX_ALERT_LEAD_DAYS` | int | `7` | Lead window (days) for notification deadline reporting: surface CRITICAL/HIGH notifications whose appeal_deadline falls within the next N days |
| `CADRUMO_INBOX_DIR` | Path | (derived) | Directory where the persisted Inbox JSON file lives |
| `CADRUMO_INBOX_PDF_DIR` | Path | (derived) | Directory where downloaded notification PDFs are stored |
| `CADRUMO_INVOICES_DIR` | Path | (derived) | Directory where the invoice catalogue JSON file is stored |
| `CADRUMO_IVA_CATALOGUE_ROOT` | Path | (derived) | Root directory for the hand-reviewed IVA taxonomy catalogue |
| `CADRUMO_JUSTIFICANTE_PARSER_BACKEND` | JustificanteParserBackendSetting | `pdfplumber` | Parser backend for `cadrumo.adapters.inbound.justificante` |
| `CADRUMO_JUSTIFICANTES_DIR` | Path | (derived) | Directory where parsed justificante PDFs and metadata are stored |
| `CADRUMO_KEYRING_PROBE_TIMEOUT_S` | float | `10.0` | Wall-clock budget (seconds) for the AUTO backend's OS-keychain read before it is treated as locked. macOS Keychain ACLs are per-binary, so a process distinct from the one that minted the item must answer an authorization dialog that a headless or background context can never show, and the read would otherwise block forever. Generous enough that a foreground operator can answer the prompt; short enough that a dialog-less context degrades promptly instead of hanging |
| `CADRUMO_LIBREOFFICE_EXECUTABLE` | Path | unset | Optional explicit path to the soffice / libreoffice binary used by the workbook-parity scanner. When None the scanner resolves it from PATH. |
| `CADRUMO_LIVE_FILED_REGISTER_WALK_TIMEOUT_MS` | int | `30000` | Timeout (ms) for one AEAT filed-declaration register query for a single modelo/year. Bulk filed-history reads use this per-query budget so one slow modelo cannot block all later modelos from returning typed failures. |
| `CADRUMO_LIVE_IVA_CANCELLATION_DRAIN_MS` | int | `250` | Drain delay (ms) after a bounded live IVA read surface is cancelled, giving Playwright browser tasks time to report cancellation-only errors before the loop handler is restored. |
| `CADRUMO_LIVE_IVA_CLI_WATCHDOG_TIMEOUT_MS` | int | `240000` | Top-level CLI watchdog timeout (ms) for the combined read-only IVA remote-state command. This must exceed the normal auth and surface budgets but remain below operator shell/tool timeouts so the CLI can cancel and clean up inside its own process. |
| `CADRUMO_LIVE_IVA_DECLARATION_CAPTURE_TIMEOUT_MS` | int | `120000` | Timeout (ms) for one Modelo 303 filed-declaration observation inside a combined live IVA filed-history read. Must be lower than the outer live IVA surface timeout so partial filed-history failures can return a structured report before the whole surface is cancelled. |
| `CADRUMO_LIVE_IVA_SURFACE_TIMEOUT_MS` | int | `180000` | Outer timeout (ms) for each live IVA read surface inside a combined remote-state acquisition. Individual browser stages have their own shorter timeouts; this bounds the whole filed-history or wallet/cartera surface. |
| `CADRUMO_LIVE_TESTS_ENABLED` | str | empty | Opt-in flag (set to '1') to run @pytest.mark.aeat_live tests against real external services |
| `CADRUMO_LIVE_TESTS_GOOGLE` | str | empty | Opt-in flag (set to '1') to run @pytest.mark.aeat_live Google (OAuth / Drive) tests against real Google services |
| `CADRUMO_LLM_ANTHROPIC_API_KEY` | SecretStr | (secret) | Anthropic API key (env only, never logged) |
| `CADRUMO_LLM_CACHE_DIR` | Path | (derived) | Directory for on-disk LLM cache entries |
| `CADRUMO_LLM_CACHE_MAX_RECORDS` | int | `5000` | Maximum number of LLM response-cache entries retained; oldest excess entries are pruned |
| `CADRUMO_LLM_CACHE_RETENTION_DAYS` | int | `30` | Retention window in days for on-disk LLM response-cache entries; older entries are pruned |
| `CADRUMO_LLM_DEFAULT_MAX_TOKENS` | int | `1024` | Default maximum output tokens when an LLM request omits ``max_tokens`` |
| `CADRUMO_LLM_DEFAULT_TEMPERATURE` | float | `0.0` | Default sampling temperature when an LLM request omits ``temperature`` |
| `CADRUMO_LLM_DEFAULT_TIMEOUT_S` | int | `60` | Default timeout for LLM provider calls in seconds |
| `CADRUMO_LLM_GEMINI_API_KEY` | SecretStr | (secret) | Google Gemini API key (optional) |
| `CADRUMO_LLM_GEMINI_GENERATE_CONTENT_TEMPLATE` | str | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | Google Gemini generateContent endpoint template (``{model}`` is substituted) |
| `CADRUMO_LLM_MAX_RETRIES` | int | `3` | Maximum retry attempts for retryable LLM failures |
| `CADRUMO_LLM_MODEL` | str | `claude-sonnet-4-6` | Default LLM model identifier |
| `CADRUMO_LLM_OLLAMA_CHAT_URL` | str | `http://127.0.0.1:11434/api/chat` | Local Ollama /api/chat endpoint; override for non-localhost Ollama deployments |
| `CADRUMO_LLM_OLLAMA_NUM_CTX` | int | `8192` | Ollama context window (num_ctx) for local requests. The vision read sends the full registry allow-list prompt plus the encoded invoice image, which exceeds Ollama's 4096 default; 8192 fits the prompt + image + output with headroom and still runs on consumer hardware |
| `CADRUMO_LLM_OLLAMA_VISION_MODEL` | str | `qwen2.5vl:3b` | Local Ollama vision model used to read scanned/image evidence on-host (the default, gestor-allowed posture); must be a multimodal model pulled into the local Ollama runtime. Default qwen2.5vl:3b (~3 GB) is document/OCR-grade and runs on normal consumer hardware (modest GPU or CPU); override to qwen2.5vl:7b for an 8 GB+ GPU or moondream for CPU-only/low-memory hardware |
| `CADRUMO_LLM_OPENAI_API_KEY` | SecretStr | (secret) | OpenAI API key (optional) |
| `CADRUMO_LLM_OPENAI_CHAT_COMPLETIONS_URL` | str | `https://api.openai.com/v1/chat/completions` | OpenAI Chat Completions endpoint; override for OpenAI-compatible proxies |
| `CADRUMO_LLM_PROVIDER` | LLMProviderSetting | `ANTHROPIC` | Default LLM provider name |
| `CADRUMO_LLM_RUN_TELEMETRY_DIR` | Path | (derived) | Directory for append-only local LLM run-timing telemetry logs |
| `CADRUMO_LLM_RUN_TELEMETRY_MAX_RECORDS` | int | `5000` | Maximum number of local LLM run-telemetry records retained; oldest excess records are pruned |
| `CADRUMO_LLM_RUN_TELEMETRY_RETENTION_DAYS` | int | `30` | Retention window in days for local LLM run-telemetry records; older records are pruned |
| `CADRUMO_LLM_USAGE_DIR` | Path | (derived) | Directory for append-only LLM usage JSONL logs |
| `CADRUMO_LLM_USAGE_MAX_RECORDS` | int | `5000` | Maximum number of LLM usage records retained; oldest excess records are pruned |
| `CADRUMO_LLM_USAGE_RETENTION_DAYS` | int | `30` | Retention window in days for LLM usage records; older records are pruned |
| `CADRUMO_LLM_VISION_READ_TIMEOUT_S` | int | `300` | Per-request timeout for the on-host local vision read; larger than the general LLM timeout because a local vision model on consumer hardware (CPU or a modest GPU) can take one to several minutes to read an invoice |
| `CADRUMO_LOCAL_STORAGE_ROOT` | Path | (derived) | Root directory for the LocalFileSystemProvider backend. Each namespace becomes a subdirectory; each object is a `<hmac_prefix_8>--<label>.bin` file paired with a `.meta.json` sidecar. The default is installed-run aware: a source checkout resolves to `PROJECT_ROOT/var/storage`, while an installed distribution roots at the platform user-data directory (`%LOCALAPPDATA%/cadrumo/storage`, `$XDG_DATA_HOME/cadrumo/storage` or `~/Library/Application Support/cadrumo/storage`) so the encrypted store never lands inside a virtualenv or uv cache. An explicit `CADRUMO_LOCAL_STORAGE_ROOT` override wins over the derived default. |
| `CADRUMO_LOG_DIR` | Path | unset | Diagnostic-log root directory. The ``None`` default here is a placeholder: when the field is not explicitly set, the model validator roots it at ``<cadrumo_local_storage_root>/logs`` so the diagnostic log lives under the one state root that ``CADRUMO_LOCAL_STORAGE_ROOT`` scopes, isolating each workspace's log. An explicit ``CADRUMO_LOG_DIR`` override wins over the derived default. |
| `CADRUMO_LOG_FILE_BACKUP_COUNT` | int | `5` | Number of rotated cadrumo.log backups retained by the rotating file handler |
| `CADRUMO_LOG_FILE_LEVEL` | str | `DEBUG` | Log level for the file handler installed by ``cadrumo.core.logging`` |
| `CADRUMO_LOG_FILE_MAX_BYTES` | int | `10485760` | Size cap (bytes) for cadrumo.log before the rotating file handler rolls over; default 10 MiB |
| `CADRUMO_LOG_LEVEL` | str | empty | Optional default CLI log level override: quiet, default, verbose, or debug |
| `CADRUMO_LOG_ROOT_LEVEL` | str | `DEBUG` | Root logger level installed by ``cadrumo.core.logging`` |
| `CADRUMO_LOG_STDERR_LEVEL` | str | `ERROR` | Log level for the stderr handler installed by ``cadrumo.core.logging`` |
| `CADRUMO_M210_ENGINE_LIVE` | bool | `false` | Gate the M210 IRNR engine, which currently covers only TRLIRNR Art. 25 letters a, b, and f. When False (default) `aeat app modelo work create --modelo 210` emits the Path-B refusal stub. When True the stub guard is skipped and the engine path runs (irnr_resolve_tipo_gravamen dispatch + representante-fiscal predicate + cuota composition). |
| `CADRUMO_MANUALS_HTTP_TIMEOUT_S` | float | `60.0` | HTTP timeout (seconds) for AEAT manual PDF downloads |
| `CADRUMO_MANUALS_REVIEW_REQUIRED` | bool | `true` | When True, manual corpus verification rejects any Manual/Section/Rule record missing definition-review metadata; when False the rejection is downgraded to a warning |
| `CADRUMO_MCP_SERVING_CONCURRENCY` | int | `4` | Maximum MCP tool calls dispatched off the event loop at once. Bounds the supervised subprocess spawn and the warm in-process worker pool so a burst cannot thrash the host; the previous anyio default admitted 40. A conservative small default suits the single-operator desktop client; raise it for a multi-client host. |
| `CADRUMO_MCP_STDIO_WATCHDOG` | bool | `true` | Whether the MCP stdio server anchors its lifetime to the client process. The stdio contract is 'exit on stdin EOF', but on Windows an inherited pipe handle can keep stdin open after the spawning client is gone, so EOF never arrives and the server runs indefinitely - holding its warm caches and never running the interpreter-exit hooks that zeroise bound bucket sessions. The watchdog reaps the server when its client dies. Disable only to diagnose the watchdog itself: with it off, stdin EOF is the sole exit path and a leaked server is unreapable. |
| `CADRUMO_MCP_WARM_CAPTURE_WAIT_SECONDS` | float | `5.0` | How long a warm in-process MCP call waits for the stdout-capture lock before degrading to the supervised subprocess transport. Bounds the blast radius of a slow or hung in-process verb: a call never queues forever behind the capture. Comfortably covers a normal warm call's sub-second-to-low-single-digit hold. |
| `CADRUMO_MCP_WEDGE_THRESHOLD_SECONDS` | float | `180.0` | When a warm in-process call has held the stdout-capture lock past this many seconds the warm transport is declared wedged and subsequent READ/MUTATE calls route straight to the supervised subprocess (a warning Notice names the wedge) until the wedged worker completes. Defaults to the MUTATE tier ceiling, the longest an in-process call may legitimately run. |
| `CADRUMO_OUTPUT_LANGUAGE` | OutputLanguage | `es` | Target ISO 639-1 language code for user-facing content. Invalid values coerce to None and fall back to the default. |
| `CADRUMO_PROXY_BYPASS` | str | empty | Comma-separated list of domains to bypass the proxy |
| `CADRUMO_PROXY_PASSWORD_SECRET` | SecretStr | (secret) | Password for proxy authentication |
| `CADRUMO_PROXY_URL` | str | empty | Proxy URL (e.g., 'http://proxy.example.com:8080') |
| `CADRUMO_PROXY_USERNAME` | str | empty | Username for proxy authentication |
| `CADRUMO_RATE_LIMIT_DELAY_SECONDS` | float | `2.0` | Minimum delay between AEAT requests in seconds |
| `CADRUMO_REGISTRY_DISK_CACHE_DIR` | Path | unset | Override for the cross-process registry disk-pickle directory. When unset, production derives <cadrumo_local_storage_root>/cache/registry and pytest runs share the host temp directory for the immutable bundled-root pickle. Set only by test isolation to redirect the cache onto a test-owned directory, so a test asserting exclusive pickle state never races sibling pytest-xdist workers. |
| `CADRUMO_REGISTRY_DISK_CACHE_MAX_ENTRIES` | int | `8` | Maximum number of registry disk-cache pickles retained per cache directory; after each write the oldest excess pickles are pruned (best-effort) so accumulated per-fingerprint pickles cannot grow without bound. |
| `CADRUMO_REGISTRY_PARITY_STORE_DIR` | Path | (derived) | Directory where registry parity tape artifacts are archived by default |
| `CADRUMO_REPLAY_ACTIVE` | str | empty | Subprocess-IPC marker carrying the original run_id when a CLI invocation is a replay re-entry |
| `CADRUMO_RUNS_DIR` | Path | (derived) | Directory where run traces and JSONL event logs are persisted (one subdirectory per run_id, containing trace.json + events.jsonl) |
| `CADRUMO_RUNS_MAX_TOTAL_BYTES` | int | `268435456` | Trace-store byte cap; after age pruning, remove oldest runs but always retain the newest |
| `CADRUMO_RUNS_RETENTION_DAYS` | int | `30` | Retention window in days for per-run trace directories; older run directories are pruned |
| `CADRUMO_SECRET_PASSPHRASE` | SecretStr | (secret) | Passphrase that derives the encrypted-secret-store master key. Default None — the master-key loader refuses operation on None or empty value to preserve fail-closed behaviour. Operator-facing env var is CADRUMO_SECRET_PASSPHRASE. |
| `CADRUMO_SECRET_STORE_BACKEND` | SecretStoreBackend | `auto` | Master-key backend for the secret store. auto = OS keychain when available, encrypted file fallback otherwise. keyring = OS keychain only (refuses to fall back). file = encrypted file only (required for CI / headless). unsecured = testing-only mode with a published deterministic key; requires cadrumo_allow_unencrypted=true and refuses real NIFs. |
| `CADRUMO_SECRET_STORE_DIR` | Path | (derived) | Directory for the encrypted secret-store master-key file and ciphertext records |
| `CADRUMO_STATUS_CACHE_DIR` | Path | (derived) | Directory for the short-lived AEAT status-page cache |
| `CADRUMO_STATUS_CACHE_TTL_S` | int | `900` | TTL in seconds for status cache entries (default 15 min) |
| `CADRUMO_STORAGE_BACKUP_DIR` | Path | (derived) | Directory where the storage layer writes database backups |
| `CADRUMO_STORAGE_PROVIDER_KIND` | str | `local_filesystem` | Backend for `cadrumo.adapters.outbound.storage`. Accepted values: local_filesystem (default), google_drive, in_memory. google_drive additionally requires cadrumo_google_drive_root_folder_id and a per-profile registered OAuth client + token via `aeat config google`. |
| `CADRUMO_STRICT_SECURITY` | bool | `false` | Raise instead of warn when AEAT credential artifact permission hardening fails |
| `CADRUMO_SUBMISSIONS_DIR` | Path | (derived) | Directory where ModeloPresentado JSON audit records are persisted |
| `CADRUMO_TELEMETRY_ENDPOINT` | str | unset | Remote telemetry collector URL, consumed by HttpTelemetrySink when a call site opts into real transmission. Unset means no dial target. |
| `CADRUMO_TELEMETRY_GESTOR_MODE` | bool | `false` | Gestor/professional deployment flag. When True, remote telemetry emission is categorically refused regardless of cadrumo_telemetry_opt_in, cadrumo_telemetry_tier, or per-invocation consent. |
| `CADRUMO_TELEMETRY_OPT_IN` | bool | `false` | Whether this deployment permits transmitting remote telemetry at all. Default off: all telemetry stays local. When True, a per-invocation operator consent acknowledgement is still required for each emit, and cadrumo_telemetry_tier must not be 'off'. |
| `CADRUMO_TELEMETRY_TIER` | TelemetryTier | `off` | Remote telemetry tier: 'off' (no remote emission regardless of opt-in), 'crash_only' (error/outcome counters only), or 'full' (counters plus timing percentiles). Only remote_allowed=True metric keys are ever eligible for transmission at any tier. |
| `CADRUMO_TOKEN_DIR` | Path | (derived) | Directory for cached authentication token and lock files. The ``PROJECT_ROOT`` default here is a placeholder: when the field is not explicitly set, the model validator roots it at ``<cadrumo_local_storage_root>/tokens`` so every profile store, token and lock files included, lives under one state root. An explicit ``CADRUMO_TOKEN_DIR`` override wins over the derived default. |
| `CADRUMO_TUI_APPEARANCE` | TuiAppearance | `auto` | Appearance for the full-screen terminal surfaces. auto = follow the host terminal. light = the warm-paper appearance. dark = the low-light appearance. |
| `CADRUMO_USAGE_RATIOS_PATH` | Path | (derived) | User-configured per-category usage ratio overrides |
| `CADRUMO_VALIDATION_VERDICT_CACHE_DIR` | Path | (derived) | Directory for the persistent registry-validation verdict cache (a fingerprint-keyed proof that validate_registry ran green, so a matching immutable tree skips runtime re-validation) |
| `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR` | Path | unset | Opt-in diagnostic capture directory for the IVA compensation wallet (cartera) read. The ``None`` default disables capture and is the only production posture: with it unset the wallet read path is byte-for-byte unchanged. When set via ``CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR`` the read dumps the full captured page tree — main document, every popup page, every child frame, and per-page screenshots — to this directory so AEAT DOM drift on the cartera surface can be diagnosed offline against real evidence. The capture may contain live taxpayer amounts; it is written only to this operator-chosen directory and must never be committed or reused as a fixture without sanitisation. |
| `CADRUMO_WALLET_DIAGNOSTIC_RETENTION_DAYS` | int | `30` | Retention window in days for wallet diagnostic dump files; when the opt-in dump directory is configured, dump files older than this are pruned |
| `CADRUMO_WORKBOOK_PARITY_LIBREOFFICE_TIMEOUT_S` | int | `120` | Subprocess timeout (seconds) for the LibreOffice binary XLS conversion fall-back |
| `CADRUMO_WORKBOOK_PARITY_PER_FILE_TIMEOUT_S` | float | `15.0` | Default per-file timeout (seconds) for workbook-parity scans |
| `CADRUMO_WORKBOOK_PARITY_RECALC_TIMEOUT_S` | int | `60` | Subprocess timeout (seconds) when forcing workbook recalculation |
| `CADRUMO_WORKFLOW_RUNS_DIR` | Path | (derived) | Directory where WorkflowResult JSON audit records are persisted |
| `FINANCIAL_BASE_CURRENCY` | str | `EUR` | Fallback ISO 4217 currency used when a financial source omits a per-row currency |
| `FINANCIAL_DEFAULT_CSV_ENCODING` | str | `utf-8` | Preferred encoding attempted first when decoding financial CSV sources |
| `NO_COLOR` | bool | `false` | Disable ANSI colour output regardless of TTY state. Mirrors the widely-adopted no-color.org convention via the NO_COLOR environment variable; pydantic-settings reads NO_COLOR (uppercased field name) out of os.environ on Settings() instantiation, so the no-color convention is honoured without per-call-site os.environ reads. |
| `SITE_HEALTH_PROBE_URL` | str | (derived) | AEAT Sede URL the site-health probe navigates to |
| `SITE_HEALTH_RATE_LIMIT_RETRY_AFTER_DEFAULT` | int | `300` | Fallback Retry-After seconds when a 429/503 omits the header |

Secrets are never printed by the application and are marked `(secret)` above.
Defaults marked `(derived)` are computed from the storage root or project
location at runtime.
