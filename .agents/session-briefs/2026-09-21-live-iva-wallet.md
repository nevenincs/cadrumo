# Live AEAT wallet: backend, CLI and TUI brief

Brief ID: LIVE-WALLET-01. Revision: 0.1. Date: 2026-09-21.
Feature: Cartera de cuotas de IVA a compensar. This is a protected read-only AEAT service, not a new modelo implementation.
Status: official-service research and three bounded Luna Max source reports complete. Bounded readiness checks completed; live authentication and acquisition BLOCKED before browser launch. No live auth attempt or wallet result was obtained.
Session name: `live-iva-wallet`. Goal: prove one real authenticated wallet read through the existing backend, then close demonstrated CLI/TUI configuration and feature gaps without duplicating the driver.
Provider, lead model, cc number and UUID: pending user assignment.
Required instructions: [session policy](session-policy.md), revision 1.5, and [ACCEPTANCE-01](acceptance-pattern.md), revision 1.4, including its explicit live read-only exception. Current live reservation/checkpoint: [live wallet preflight](handoffs/live-wallet-preflight.md).

## Questions and current answers

| Question | Evidence now | What remains unproven |
| --- | --- | --- |
| Does live pull exist? | Yes: canonical Playwright wallet adapter, parser/schema, encrypted observation storage, reconciliation and CLI commands. | A fresh successful pull for this user, deployment and current AEAT page. |
| Is the driver verified? | Focused parser/navigation/guard tests and opt-in live tests exist. | Test source is not an executed result. No current live pass receipt was inspected or produced. |
| Can the user configure authentication? | CLI exposes profile, AEAT provider and local custody workflows. Certificate, Cl@ve Móvil and Cl@ve Permanente are declared providers. | Installed-path setup for the user's existing credentials; each provider's actual live readiness. No TUI AEAT-provider/certificate setup form was found. |
| Can both frontends pull/display the wallet? | CLI has pull/history. | No TUI wallet route/action found. CLI success alone cannot establish parity. |
| Do the supplied NIE/support values yield results? | These are supported non-QR identity inputs. | Configuration must actually load, the active encrypted profile must be available and consistent, a Móvil route must be recorded, and authentication must complete. Presence of two values is not an authenticated session. |

## Service meaning and scope

AEAT offers the wallet both within Pre303 and as a standalone consultation. It describes carry-forward credit by origin year/period and its relationship to Modelo 303 casillas 110, 78 and 87. This is not the taxpayer's complete payable/debt/payment/refund account and not an SII invoice book. [AEAT wallet explanation](https://sede.agenciatributaria.gob.es/Sede/iva/pre-303/preguntas-frecuentes/cuestiones-especificas-sobre-servicio-pre303_.html), [AEAT consultation entry](https://sede.agenciatributaria.gob.es/Sede/iva/regimenes-tributacion-iva/gestiones.html).

The current canonical row schema describes the consulted surface as available balance per origin period. `generated_amount` and `applied_amount` may remain absent; do not invent them from `pending_amount`, or infer movement history from one snapshot. Preserve actual page/schema evidence if AEAT changes what it exposes.

AEAT's documented Cl@ve Móvil routes include QR and non-QR DNI/NIE plus contrast data. The NIE support number is contrast data; the user still confirms the request in the app, with an SMS alternative described by AEAT. This does not prove the product implements every alternative. Cl@ve Permanente is a distinct provider, not another name for Móvil. [AEAT identification instructions](https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/firma-digital-sistema-clave-pin-tecnica/obtencion-clave-pin.html), [official Cl@ve Permanente explanation](https://clave.gob.es/clave-permanente/como-funciona).

First live scope: the user's own authenticated wallet only. No represented taxpayer, filing, draft modification, payment, credit application, refund request, unrelated acquisition or credential reset. The user confirmed exclusive AEAT-login availability and willingness to approve a mobile request. Reserve one owner and request approval once, only when ready. User confirmation of exclusivity is not a successful login.

Use an explicit current consultation year/period selected through the existing period contract, not the income-tax scenario's latest completed year and not a hardcoded documentation example. On this research date, a current-quarter query is 2026/3T; confirm the service's supported query semantics before execution. A wallet snapshot's capture time and origin periods are distinct coordinates. Never relabel an old cached observation as current.

## Existing owners — reuse before implementation

Source anchor observed: `57595ff38871cc87bfb703653074c8521e27f20a`, worktree `tui/modelo`, with concurrent income/export edits. The source anchor is orientation, not a completeness oracle. Three Luna reports cover driver/storage, auth/configuration, and frontend surfaces. The coordinator inspected critical CLI output, schema, authentication-route, parser-error and live-test contracts directly. Recheck only affected deltas at dispatch.

Paths below are relative to `src/cadrumo/` unless prefixed with `docs/`.

| Owner | Source evidence | Required reuse/boundary |
| --- | --- | --- |
| Playwright wallet reader | `adapters/outbound/aeat/sede/iva_compensation_wallet.py:132`, `:170`, `:259`, `:306`, `:985`. | Existing authenticated traversal, own-name gate, read-query execution and landing guards. Do not create a parallel scraper or weaken write guards when a route changes. |
| Parsing and base schemas | `adapters/outbound/aeat/sede/iva_compensation_wallet_parsing.py:82`, `:98`; `schema.py:307`. | Strict wallet rows/observation, decimal meaning, identity, target period, source URL and capture time. Extend the canonical schema only for evidenced data; no UI-specific wallet DTO that changes tax meaning. |
| Application capture | `application/live/iva_remote_state.py:85`; `entrypoints/live_state_composition.py:536`. | Existing capture, secure persistence/reload and reconciliation. No second wallet storage/reconciliation path. |
| Secure evidence | `adapters/outbound/aeat/sede/observation_store.py:96`, `:377`; `entrypoints/live_state_composition.py:571`. | Approved encrypted bucket-backed observations and artifacts. Logical secure-object references are not permission to write payloads as plaintext files. |
| Authentication contracts | `core/auth_provider.py:17`; `application/auth/sessions.py:379`, `:645`; `adapters/outbound/aeat/auth/session_store.py:1`. | Canonical provider types, identity binding, persisted route, encrypted session reuse. Local profile unlock and AEAT authentication remain separate. |
| CLI feature | `entrypoints/cli/_app_live_iva_wallet_command_specs.py:52`; `_app_live.py:126`, `:194`. | Use the existing command registration/application operation. User-facing output includes amounts; it is NOT safe to stream directly into agent tool output. |
| CLI configuration | `entrypoints/cli/_auth_command_specs.py:135`, `:346`; `_custody_command_specs.py:61`; `profile_command_specs.py:457`. | Existing provider/profile/certificate/secret workflows, machine-secret channels and readiness. Do not add an ad-hoc dotenv editor or second credential store. |
| TUI gaps | `entrypoints/tui/aeat_sync/routes.py:44`, `workspace_reader.py:88`; `profile/acquisition_sources.py:38`; `launcher.py:456`. | Existing AEAT Sync routes have no wallet action. Profile acquisition cards concern census/filed history; launcher does not wire the acquisition callback/credential posture identified by discovery. Extend shared composition; do not call CLI internals. |
| Local IVA comparison | `domain/iva_compensation/balance.py`, `carry_forward.py`, `reconciliation.py`. | IVA-01 owns settlement semantics. Consume wallet evidence/decisions through its existing contract; do not redesign compensation accounting under this live-feature brief. |

### Authentication/configuration matrix to prove

| Capability | Current source finding | Acceptance requirement |
| --- | --- | --- |
| Active taxpayer/profile and local secure unlock | Profile/custody CLI exists; TUI supports local registration/login/profile editing. | Select the intended profile; verify identity match without printing it; preserve existing secrets and data. No implicit profile creation/reset. |
| Cl@ve Móvil non-QR | DNI/NIE plus contrast settings and `app_request` route; user confirmation required. | This is the first requested live route. Profile route and readiness must be accessible and actionable from both frontends. |
| Cl@ve Móvil QR | Canonical `qr` route exists. | Determine whether the actual UI can display the challenge safely and wait/cancel. Do not put QR material into agent transcripts. Source support is not a live pass. |
| Cl@ve Permanente | Declared provider and identifier/password settings exist. | Correct secure configuration and readiness/refusal from each frontend. Do not claim tested without its own authorized credentials/run. |
| Certificate | Declared provider, certificate registration and secret backend exist. | Certificate discovery/selection, password channel, validity/identity diagnostics and readiness; distinguish metadata from working browser authentication. |
| SMS/PIN and DNIe | AEAT documents alternatives; reserved product tokens are not implemented provider evidence. | Report supported, unsupported or unverified precisely. Do not advertise standalone `clave_pin`/`dnie_pkcs` as working providers or infer an SMS fallback from Móvil support alone. |

Relevant configuration NAMES only: `CADRUMO_AUTH_PROVIDER`; `CADRUMO_CLAVE_MOVIL_DNI_NIE`, `CADRUMO_CLAVE_MOVIL_DNI_FECHA`, `CADRUMO_CLAVE_MOVIL_NIE_SOPORTE`, `CADRUMO_CLAVE_PREFER_NON_QR`, `CADRUMO_CLAVE_MOVIL_TIMEOUT_MS`; `CADRUMO_CLAVE_PERMANENTE_DNI_NIE`, `CADRUMO_CLAVE_PERMANENTE_PASSWORD`; `CADRUMO_CERTIFICATE_PATH`, `CADRUMO_CERTIFICATE_PASSWORD_SECRET`. Local custody's `CADRUMO_SECRET_PASSPHRASE` is not an AEAT password. Secret CLI inputs use supported stdin/fd contracts; never substitute argument values.

Important loading distinction: `docs/reference/environment-overrides.md:13` says the application reads process environment. Repository tests bridge `env/.env` through conftest, but production does not auto-load it. Neither root `.env` nor `env/.env` exists in this worktree at the metadata check. The user authorized a bounded search under `Y:/code` for the supplied environment/secret source; inspect filenames and expected-key presence only, not raw values. Use an established explicitly scoped launcher/environment mechanism; never execute dotenv content as shell code. Profile-borne credentials take precedence over environment, and `_prepare_clave_auth()` requires a persisted Móvil route when applicable. Test actual effective configuration, not merely file presence. Do not treat `CADRUMO_ACTIVE_PROFILE` as an implemented env setting.

Canonical encrypted profile selectors are `auth.dni_nie`, `auth.numero_soporte`, `auth.fecha_validez` and `auth.clave_movil_route`; the non-QR app route is `app_request`. Existing `aeat config auth status --provider clave_movil` and the live preflight projection expose readiness/presence through `application/auth/operator.py` and `entrypoints/cli/_app_live_auth_preflight.py`. Agent receipts still allowlist only safe booleans/status: status output can contain profile metadata. `resolve_clave_credentials` in `application/auth/sessions.py:717` owns profile-first/environment fallback; do not invent a second secret lookup.

### Actual readiness results from this preflight

- The six inspected process-env fields were absent/empty: auth provider, Móvil DNI/NIE, NIE support number, DNI date, prefer-non-QR and local secret passphrase. This does not establish whether encrypted profile credentials exist.
- Authorized filename discovery under `Y:/code` found relevant `env/.env` candidates in `cadrumo-worktrees/main`, `cadrumo-worktrees/load-authority` and `cadrumo-worktrees/cartera`. In all three, the assignments for `CADRUMO_CLAVE_MOVIL_DNI_NIE`, `CADRUMO_CLAVE_MOVIL_NIE_SOPORTE`, `CADRUMO_SECRET_PASSPHRASE` and `CADRUMO_AUTH_PROVIDER` were present but empty. The final check was independently verified; an earlier failed scanner result was discarded. No raw file contents/values were reported. An uninspected archived candidate is not evidence of usable credentials, and the scan is not proof no other secret source exists.
- `uv` is available. `uv run --no-sync aeat --help` and `uv run --no-sync aeat app live iva-wallet pull --help` both exited 2; raw diagnostics were suppressed and the exact cause of those invocations was not retained. Do not invent their error text.
- Independent targeted checks established that this worktree's `.venv/Scripts/python.exe` exists, `.venv/Scripts/aeat.exe` does not, and that interpreter's `importlib.util.find_spec('cadrumo')` returns no module. `pyproject.toml:134` declares the intended `aeat` bootstrap entry point. This confirms a local runtime prerequisite is missing, regardless of the unretained help diagnostic.
- No dependency installation/sync, profile/config change, credential copying, login, browser launch, live test or wallet query was performed. Saved encrypted credential presence and profile route remain unknown because the supported application path was not available.

Next authorized implementation-session prerequisite: provision the source-corresponding runtime through the established project workflow, then use canonical encrypted-profile readiness access. Do not recreate credentials just because dotenv assignments are empty; the user believes the values are already saved as secrets. Reacquire the login reservation and user availability before any actual request. This preflight did not silently switch to another worktree's installation or bypass encrypted custody.

## Live safety and proof ladder

1. **Readiness:** establish source-corresponding executable, supported configuration loading, provider/route, active profile identity and encrypted-custody availability. Report presence/readiness booleans only. No browser yet if these are incomplete.
2. **Safe execution boundary:** normal CLI wallet output contains financial values. Capture it in memory and emit only allowlisted stage/status/assertion fields, or use an existing equivalently safe runner. Do not introduce a second authentication/Playwright implementation. Audit logging before execution: suppressing terminal output does not sanitize a file logger.
3. **One authentication attempt:** reserve browser/login, finite timeout and retry limit. Reuse a valid session if the existing provider proves it valid; label `reused_session`, not `fresh_login`. Notify the user when their app approval is actually requested. Do not ask them to paste an OTP/password or share a QR screenshot in chat. Stop on rejection, expiry or an unknown challenge.
4. **Protected wallet read:** prove the correct service and acting identity, then use only the existing guarded consultation. A wallet form POST can be a read query; HTTP method alone does not prove a filing mutation or safe behavior. Never broaden allowed routes to make navigation pass.
5. **Result and validation:** identify a genuine result or explicit no-credit state, parse the real table through canonical schemas, validate period/identity and compare row/total meaning independently. A login page, unavailable service, parse failure and zero balance are different outcomes. Inspect all applicable rows/pagination rather than silently accepting partial data.
6. **Secure observation and presentation:** persist/reopen through approved encryption, preserve source/capture identity, inspect status/freshness and reconcile through existing policy. The local UI may show the user their financial values; reports and receipts expose only safe assertions/opaque evidence references. Successful capture and a blocked reconciliation decision are separate results.
7. **Cleanup and handoff:** close owned contexts/processes, apply existing secure session retention, release the login reservation, and report each stage truthfully. No deletion of user credentials, certificate, profile or supplied `.env`.

Known safety concerns to resolve before any unfiltered live run:

- `_app_live.py:155` and `:175` emit `total_pending`, `selected_amount` and local comparison amounts. This is expected product presentation, not a sanitized agent receipt.
- `iva_compensation_wallet_parsing.py:611` includes raw malformed amount text in certain exceptions/context. Determine whether user-error/log serializers redact before storage/output; do not assume they do. Test failures on synthetic malformed values first. A private live traceback must never be written to plaintext logs.
- Existing wallet diagnostics are opt-in structural summaries (`iva_compensation_wallet.py:873`), not raw HTML, but they have retention pruning. Do not point diagnostics at another session's directory or enable unnecessary captures.
- Cl@ve failure evidence may contain HTML/screenshots under its encrypted diagnostics mechanism. Verify all actual trace/video/download/session-state paths, not just wallet observation encryption.
- Existing live pytest tests interpolate exceptions in failure messages. They are not automatically safe real-user capture runners merely because they have an opt-in marker.

## Acceptance checks

| ID | Check | Evidence required |
| --- | --- | --- |
| LW1 | Configure actual prerequisites | CLI and TUI provider/route/profile/custody setup and safe status/refusal. Effective configured values loaded from the supported source; no secrets in output. |
| LW2 | Authenticate | One observed accepted mobile flow or explicitly validated reused session; cancellation/expiry/identity mismatch handled. Auth success alone does not pass LW3. |
| LW3 | Pull actual wallet | Protected AEAT wallet reached; actual result/explicit empty state parsed under canonical schema; source identity and capture freshness proved. No fixture/cache substitution. |
| LW4 | Preserve financial meaning | Locale/decimal precision, origin periods, row coverage and total reconciliation; absent generated/applied fields stay absent. Do not hardcode an expected private balance. |
| LW5 | Persist securely | Observation/evidence encrypted and reopenable; no plaintext secrets/private payloads in subprocess output, logs, screenshots, traces or temporary files. |
| LW6 | Inspect and refresh | Both frontends expose wallet status/history, amounts to the local user, source time and explicit refresh. Cached versus fresh is visible; refresh does not duplicate or erase evidence. |
| LW7 | Configuration/provider parity | Matrix above distinguishes actually supported setup from unavailable and not live-tested modes. User can diagnose missing route/unlock/credential without traceback or secret disclosure. |
| LW8 | Reconcile, not overwrite | Reuse IVA-01's wallet/local comparison and decision contracts. Stale/missing/conflicting evidence remains visible; consultation does not silently change filed history or apply credit. |
| LW9 | Fail safely | Synthetic auth-gate redirect, unexpected landing, malformed/partial page, expired session, denied authorization, service error and genuine empty wallet. Prove no false complete/zero and no expanded write authorization. |
| LW10 | Frontend continuation and receipts | Same existing shared contracts, independent synthetic CLI/TUI checks, sequential live execution only when needed. One live receipt can support shared-backend claims; it cannot prove an unexercised TUI action. Stage outcomes and cleanup recorded without values. |

Do not require all authentication modes to work live before reporting the user's Móvil result. Conversely, do not generalize one Móvil pass into certificate/Permanente/SMS/DNIe coverage. The minimum first result is LW1-LW5 for the requested route, with frontend gaps separately reported.

## Verification and implementation cadence

Existing tests, all NOT RUN by this preflight:

- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_iva_compensation_wallet.py`: parser/guard/shape/structural diagnostic contracts. Select exact nodes such as `test_wallet_shape_context_redacts_url_query_and_input_values`, `test_wallet_diagnostic_dump_writes_only_redacted_structural_summary`, and `test_wallet_execute_gate_detection_identifies_read_query_shape` after a bounded current-source check.
- Owning wallet test files `test_wallet_diagnostic_retention.py` and `test_wallet_landing_rule_is_unconditional.py`; use exact relevant nodes, not blanket collection.
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_iva_compensation_wallet_live.py::test_fetch_iva_compensation_wallet_live_returns_read_observation`: opt-in adapter live path, with `aeat_live` and `hex_outbound_adapter` markers. It checks schema/route semantics but is not by itself CLI/TUI acceptance or a safe raw reporting path.
- `src/cadrumo/adapters/persistence/profile/tests/test_iva_wallet_live.py`: application-level live workflow. Do not run it alongside the adapter live test; both may consume the same login and duplicate acquisition.

Reserve narrow synthetic checks with explicit markers and `-n 0`. `CADRUMO_LIVE_TESTS_ENABLED` is the live opt-in gate, not authentication proof. Never enable broad live suites to discover whether one wallet read works. Use the existing uv environment without implicit dependency repair. Missing executable/runtime setup is a separate blocker, not permission to reinstall or alter another session's environment.

Implementation starts only for reproduced defects or mapped missing surfaces, under explicit file ownership. First secure the execution/reporting boundary if needed; then run the existing driver. Repair that owner if the live result exposes a defect. Add TUI wallet/auth projections through shared application/composition, preserving the CLI and established schemas. No new scraper, provider enum, secret store, wallet ledger, calculation engine or full IVA test lane. Shared auth/session/composition and IVA reconciliation files require coordination with active sessions before edits. Complete affected ty/ruff/strict-type/import gates through one aggregate owner after integration.

## Named roster and opening prompt

Every actual session follows the shared policy: `wallet-discovery` Luna Max handles bounded source/test/audit reports; `wallet-principal` Terra High (Codex) or Opus Medium (Claude) handles defined complex implementation; bounded execution workers use Terra Max or Sonnet High; exactly one `wallet-adviser` Sol High or Fable 5.1 Medium supplies architecture/optimization advice and otherwise remains idle, with no coding. Verify launcher aliases, identify the Claude-to-Luna route if needed, and record cc/UUID/owned files before dispatch. Discovery/execution workers spawn no children.

> Session live-iva-wallet. Goal: prove the existing read-only AEAT Cartera pull using the user's supported authentication, then close assigned backend-to-CLI/TUI gaps. Consume LIVE-WALLET-01, session-policy 1.5 and ACCEPTANCE-01 1.4. Reuse the Luna source map; delegate only bounded deltas. Before any login, check the live reservation and effective configuration without exposing values, establish secure output/log handling, and record one finite authentication attempt. Use the canonical driver/parser/schema and encrypted observation boundary; no parallel browser or wallet implementation. Report configuration, auth, protected read, parsing, persistence, reconciliation and frontend presentation separately. Never call fixture success, a login page, cached evidence or a written receipt a live wallet pass. Stop for missing user interaction, unsafe capture or undefined architecture; give the precise blocker and next bounded step. No remote writes beyond authentication and the guarded consultation.

Worker directive format: name; goal; exact allowed paths/actions; exclusions; dependencies; stop condition; report format. Return status, evidence/source identity, changed files if any, exact reserved checks/process/result, sanitized stage outcomes, remaining gaps and next action. Luna reports are normally <=600 words with path:line facts and proposed checks labelled NOT RUN. Preserve a compact checkpoint so compaction never triggers another login or a repeated repository sweep.
