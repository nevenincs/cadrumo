---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
---

# `live-iva-compensation-wallet` Code Review

WALLET-001 | HIGH | Public wallet reconciler accepted mismatched wallet evidence
`reconcile_iva_compensation_wallet` was exported and callable with wallet evidence whose taxpayer, year, or period did not match the requested target. This could produce a non-blocking decision from the wrong AEAT wallet observation.

Resolution: fixed. The public reconciler now validates the wallet taxpayer and target through the same target check used by the higher-level Modelo 303 reconciler. Added mismatch tests for target period and taxpayer identity.

WALLET-002 | HIGH | Modelo 303 prior compensation binding could bypass wallet reconciliation
Modelo 303 calculation accepted caller or backend values for `modelo-303-compensacion-pendiente-anteriores` when no IVA wallet reconciliation decision was supplied or persisted. This violated the accepted authority ladder for casilla `110`.

Resolution: fixed for the unsafe binding path. Modelo 303 now rejects supplied prior-compensation bindings unless a non-blocking reconciliation decision is present. Ordinary Modelo 303 calculations that do not supply prior compensation can still proceed.

WALLET-003 | HIGH | Reconciliation decision persistence overwrote prior audit state
The latest decision key was keyed only by taxpayer, target year, and target period. A later wallet pull overwrote the latest decision row and did not retain a distinct immutable decision event.

Resolution: fixed. Decision saves now write both the latest lookup row and a distinct opaque immutable audit event row. Added history loading and a two-decision roundtrip test proving latest lookup updates while immutable history keeps both decisions.

WALLET-004 | MEDIUM | Live wallet report and CLI exposed taxpayer identity
The live wallet capture report and CLI output included the taxpayer NIF/NIE in plain text. The backend evidence must keep identity inside encrypted records, but the operator report does not need to echo the identity.

Resolution: fixed for the wallet report surface. `IvaWalletCaptureReport` now exposes an opaque `taxpayer_ref` instead of `taxpayer_nif`, and the CLI emits `taxpayer_ref`.

WALLET-005 | MEDIUM | Live test skipped after live mode was explicitly enabled
The opt-in live wallet test initially skipped when Cl@ve authentication was unavailable even after the operator enabled live tests. That could hide a real auth regression.

Resolution: fixed for the new wallet live test. Once live tests are enabled, authentication failure now fails the test instead of skipping. The test remains deselected when live tests are not enabled.

WALLET-006 | MEDIUM | Existing repository tests still use pytest monkeypatch
The calculation observation repository test module already uses `monkeypatch` for database settings. This is a local test-rule mismatch outside the new wallet behavior, but it remains visible in the touched file.

Resolution: fixed. The wallet-relevant calculation observation repository tests and Sede observation-store roundtrip tests now use `override_settings` plus scoped SQL engine disposal instead of mutating process environment with `monkeypatch`.

WALLET-007 | HIGH | Explicit wallet decisions were not bound to the work-unit taxpayer
The persisted-decision path was taxpayer-scoped, but callers could pass an explicit non-blocking `iva_compensation_decision` for another taxpayer with the same Modelo 303 target year and period. `_apply_iva_compensation_decision_binding` validated target period and amount but not taxpayer identity.

Resolution: fixed. Modelo 303 calculation now passes the work-unit bucket taxpayer into the IVA wallet guard. The guard rejects explicit decisions when the bucket taxpayer is unavailable or when the decision taxpayer differs from the work-unit taxpayer. Integration tests now seed the operator profile to model the real identity binding.

WALLET-008 | HIGH | Direct casilla input could bypass wallet reconciliation for casilla 110
The previous guard blocked unsafe binding maps, but a caller could still supply `iva.compensacion-pendiente-periodos-anteriores` directly through `casilla_inputs` or `backend_casilla_inputs`. The registry runtime accepts that bound casilla as an input, so it could bypass the persisted reconciliation decision.

Resolution: fixed. The Modelo 303 guard now checks direct prior-compensation casilla inputs as well as binding maps. Without a wallet decision, any supplied prior-compensation binding or casilla value is rejected. With a wallet decision, caller/backend casilla values must match the selected decision amount.

WALLET-009 | LOW | Backend direct-casilla no-decision path lacked an explicit test
The guard implementation rejected `backend_casilla_inputs` for `iva.compensacion-pendiente-periodos-anteriores` without a wallet decision, but the focused test only covered caller `casilla_inputs`.

Resolution: fixed. Added explicit backend-casilla no-decision rejection coverage.

WALLET-010 | HIGH | Live surface needed an application-level AEAT-backed wallet verification path
The adapter live smoke test proved that the wallet driver could read a live wallet page, but it did not exercise the application-level chain that stores the wallet observation, reloads it, persists the reconciliation decision, and verifies the local Modelo 303 guard against the captured AEAT state.

Resolution: fixed. Added an opt-in live application test that uses the active profile, pulls the AEAT wallet through `capture_iva_compensation_wallet`, reloads persisted wallet evidence, loads persisted decision history, verifies wallet totals against the persisted decision, and exercises the local Modelo 303 wallet guard with the live decision. The test does not hardcode or snapshot taxpayer amounts.

WALLET-011 | HIGH | Live wallet tests did not bind the operator's secure bucket session
The direct live adapter test called the auth backend outside the CLI root callback, so encrypted Cl@ve session storage failed with no active bucket session. The application live test also inherited the unit-test storage sandbox, so it could not see the operator's active profile pointer.

Resolution: fixed. Opt-in live application tests are excluded from the application unit-test storage sandbox, and the direct live adapter/application tests explicitly bind the active master-key provider around encrypted profile/session reads. The tests now fail at the real AEAT auth boundary instead of failing locally before Cl@ve can start.

WALLET-012 | HIGH | Cl@ve Móvil non-QR verification code was rendered but not extracted
AEAT rendered the non-QR verification code in the live Cl@ve page, but the driver only checked the older configured selector and reported `verification_code_present=false`. That made live approval coordination unreliable because the operator did not receive the code needed to identify the app request.

Resolution: fixed. The Cl@ve driver now probes the configured selector with the short selector-probe timeout and falls back to extracting `Código de verificación` from rendered page HTML. Added focused coverage for the rendered non-QR HTML shape observed in live diagnostics.

WALLET-013 | HIGH | Cl@ve timeout left a server-side pending request alive
After an approval timeout, the driver closed the browser context without first asking AEAT to cancel the pending Cl@ve request. The next live attempt then failed fast with AEAT's prior-pending-request refusal.

Resolution: fixed for new attempts. On post-auth landing timeout, the driver now captures the encrypted diagnostic and then attempts to click/invoke the AEAT cancellation control before closing. The cancellation path waits for AEAT's cancellation response before logging confirmed cancellation; otherwise it logs that cancellation was requested but unconfirmed. The pending request created before this fix may still require operator rejection in the Cl@ve app or server-side expiry before another live attempt can proceed.

WALLET-014 | MEDIUM | Live test gate helper accepted values the backend rejects
The pytest helper treated any non-empty `AEAT_LIVE_TESTS_ENABLED` value as enabled, while the backend gate intentionally accepts only the literal `1`. With `true`, tests started but failed later inside the application live gate.

Resolution: fixed for the wallet live-test helper path. `requires_live_enabled()` now uses the same strict `AEAT_LIVE_TESTS_ENABLED=1` rule as the backend.

WALLET-015 | MEDIUM | Application live test writes durable local operator evidence
The application-level live wallet test intentionally exercises the production active-profile storage path. That proves the required store/reload/reconcile behavior against the current profile, but repeated live runs append encrypted wallet decision history under the operator's real local bucket.

Resolution: accepted and documented for this end-to-end live verification path. The test remains opt-in and live-gated, stores no hardcoded or source-controlled taxpayer amounts, and exists specifically to prove the production active-profile storage chain. It must not be part of default unit selection.

WALLET-016 | MEDIUM | Live tests repeated parser-local row summation
The live tests recomputed `total_pending` from parsed rows. The production parser derives the same total from the same rows, so this assertion was internal consistency rather than external oracle validation.

Resolution: fixed. The live tests no longer repeat parser-local total summation; they check structural live evidence and persistence/reconciliation relationships instead.

WALLET-017 | HIGH | Cl@ve Móvil mode intent was ambiguous during live wallet auth
Operator testimony after the live attempts: the expected production behavior is a Cl@ve Móvil app notification/approval path for the configured identity, and no notification was observed during the non-QR attempts. A later headed QR attempt opened a visible Chrome/QR page that the operator did not recognize as the expected surface. Code inspection confirms both paths exist: with `aeat_clave_prefer_non_qr=True` the driver enters the non-QR DNI/NIE fallback and waits for app confirmation; with `aeat_clave_prefer_non_qr=False` it opens the QR page. The QR attempt was a one-process diagnostic override, not the persistent profile configuration.

Resolution: recorded and pending behavioral confirmation. Persistent settings remain `aeat_clave_prefer_non_qr=True`, `aeat_browser_headless=True`, auth provider `clave_movil`, and 120 second timeout. The live wallet auth blocker is therefore not "QR is the intended default"; it is that the intended non-QR Cl@ve Móvil path reaches AEAT's wait page but does not produce an operator-observed app notification/approval completion. Next implementation work should compare the non-QR selector/form flow against the previously stable Cl@ve driver/test surface before treating wallet reads as live-verified.

WALLET-018 | MEDIUM | Configured NIE support-number path lacked focused coverage and diagnostics
The active profile uses a NIE plus support number for non-QR Cl@ve Móvil, but focused auth tests covered the DNI date branch only. Encrypted auth diagnostics also did not surface whether a failed live attempt used QR or non-QR, the identity kind, or headed/headless mode.

Resolution: fixed. Added focused non-QR NIE support-number tests, explicit rejection coverage when NIE support is missing, and redacted diagnostic metadata for auth mode, identity kind, configured contrast factors, headless/headed mode, and timeout. The operator banner now tells non-QR users to open the Cl@ve app manually because a push notification may not appear, and labels QR attempts as the QR branch.

WALLET-019 | HIGH | Auth test surface did not perform or persist live authentication
`aeat config auth test --provider clave_movil` rendered local/provider readiness only. It did not acquire a live AEAT session and did not stamp the workflow auth state after a successful session verification. This made the CLI UX misleading during live wallet work because the operator expected an authentication request while the backend had no explicit live-login command.

Resolution: fixed. Added `login_operator_auth` as the application-owned live auth entry point and exposed it as `aeat config auth login`. The service delegates to `ensure_authenticated_aeat_session`, supports persisted-session reuse, fresh login, and stale-lock reset, and records a verified session in workflow auth state without emitting identity data. The login command is locale-backed and rejects reserved providers before any live request starts.

WALLET-020 | HIGH | Operator phone-state testimony had no durable diagnostic path
The Cl@ve timeout diagnostic correctly stopped inferring the phone/app state, but the CLI had no way to attach the operator's actual observation to the encrypted diagnostic record. That left divergence analysis dependent on chat history rather than durable profile-local evidence.

Resolution: fixed. Added `aeat config auth diagnostics report DIAGNOSTIC_ID --phone-state ...` with the allowed values `app_prompted_and_accepted`, `app_prompted_not_accepted`, `app_did_not_prompt`, and `operator_did_not_check`. The application service upserts the operator report into the encrypted diagnostic payload, and diagnostics list/show now surface the recorded phone state redacted. No phone-state report has been recorded for diagnostic `20260520T152302Z` because the operator has not yet supplied that observation for the latest attempt.

WALLET-021 | HIGH | Direct wallet URL rejects the current Cl@ve driver route with AEAT 4033
After a successful Cl@ve app approval, the live wallet pull still failed when the wallet driver navigated to `https://www1.agenciatributaria.gob.es/wlpl/DAI3-RUTI/CarteraCuotas`. AEAT redirected to `erro4033.html`. The public AEAT Modelo 303 "Gestiones IVA" page links to this same wallet URL, and opening that official link without a certificate also returns AEAT 403 text stating that no electronic certificate was detected or correctly selected. Filed-history reads continue to work under Cl@ve, so this is currently isolated to the wallet surface rather than general Cl@ve auth.

Resolution: investigated and pending route correction. `capture_iva_compensation_wallet` now verifies the general Sede session first and lets the wallet driver report the concrete wallet auth-gate result, avoiding the earlier generic target-verification failure. Official AEAT Pre303 FAQ wording says Pre303 access, with its utilities, requires `Certificado o DNI electrónico o clave PIN`; therefore the live result must not be read as proof that the wallet is certificate-only. It proves only that the current direct wallet URL/driver route is wrong or incomplete for the Cl@ve-backed access path. Next implementation should discover the AEAT-supported Pre303/selector route for this exact surface before treating wallet reads as live-verified.

WALLET-022 | HIGH | Older filed Modelo 303 artefacts can capture evidence but not calculation casillas
The live filed-history register returned Modelo 303 rows for older years, but a focused capture for an older 2022 period persisted evidence with zero extracted casillas and therefore could not be promoted into IVA compensation history. By contrast, focused 2023 and 2024 captures extracted casillas and promoted into calculation observations, and full 2023/2024 history capture reloaded eight secure history rows.

Resolution: slated for parser hardening. This is not an auth failure; it is an older filed-artefact extraction coverage gap. The captured 2022 evidence is stored in encrypted secure objects and should be used to extend the filed-declaration parser without hardcoding private values in tests.

WALLET-022-RESOLUTION | HIGH | Fixed 2022 Modelo 303 submitted-file result-position extraction
Resolution: fixed for the identified 2022 page-03 result-position gap. The Modelo 303 submitted-file fallback now selects page-03 result casilla positions by filing year: 2022 reads casilla `71` at the official 2022 design position, while 2023+ keeps the newer layout. The regression test loads the bundled official 2022 AEAT record-design workbook to obtain the casilla `71` position, builds a 2022-shaped redacted record with a non-money marker at the 2023+ position, and proves extraction reads the 2022 position. No live AEAT contact or private captured values were used.

Verification:

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_declarations.py::test_modelo_303_2022_submitted_file_fallback_uses_2022_result_position src/aeat/adapters/outbound/aeat/sede/test_declarations.py::test_modelo_303_submitted_file_fallback_extracts_result_casillas src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestSubmittedFileObservation -q --disable-warnings` completed with 9 passed.
- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestSubmittedFileContext src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestSubmittedFileObservation src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestFiledObservationBindings -q --disable-warnings` completed with 15 passed.
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py` passed.

WALLET-023 | MEDIUM | Wallet and AEAT auth-gate constants were partially embedded in code/tests
The wallet adapter already obtained the direct `CarteraCuotas` path from `external_constants.toml`, but its read guard host, wallet table header tokens, AEAT host-suffix check, and `erro4033` auth-gate detection were still embedded in Python. Wallet-facing tests also repeated the direct wallet URL. That made route/auth hardening brittle and contradicted the external-constants boundary for AEAT-owned URLs, selectors, and page-shape markers.

Resolution: fixed for the current IVA wallet/Pre303 surface and adjacent live Sede surfaces. Added typed external constants for the AEAT host suffix, the generic Sede 4033 auth-gate path, Pre303 presentation-service path, Pre303 official documentation paths, Pre303 access-method wording, G313 census launcher path, and wallet table header markers. The wallet driver, NIF-IVA auth-gate detector, G313 census driver, declarations read guard, Pre303 portal entry, Mis Datos Censales portal entry, and wallet-facing tests now consume those constants through `Settings.external_constants()` or the exported canonical `IVA_COMPENSATION_WALLET_URL`. Settings defaults for the Sede origin, site-health probe URL, and certificate verification URL now derive from the same registry rather than repeating the Sede origin.

WALLET-024 | HIGH | Wallet auth still targeted the independent wallet URL instead of the Pre303 presentation service
Official AEAT wording says the wallet is available from casilla 110 inside Pre303 and also as an independent service. The first wallet implementation authenticated and verified against the independent wallet URL directly. That made the live flow depend on the same route that AEAT was returning as 4033, rather than the documented Pre303 entry point that should establish the authenticated Modelo 303 presentation context first.

Resolution: fixed and live-confirmed. The application wallet capture now requests authentication against the centralized Pre303 presentation-service URL. The Cl@ve verifier dispatches explicit target probes through AEAT's selector and actively clicks the Cl@ve option when the selector page remains visible. The wallet adapter then opens both the Pre303 presentation service and wallet URL through the selector path, continues AEAT's own-name representation gate, and only then reads the wallet page. The observed wallet source URL remains the canonical wallet URL.

WALLET-025 | HIGH | Live wallet reader stopped at AEAT's own-name representation and execute gates
After Pre303-targeted authentication succeeded, the wallet reader reached authenticated AEAT pages but not the wallet table. Live diagnostics showed two intermediate states: `DialogoRepresentacion` for own-name taxpayer selection, then the `CarteraCuotas` wallet page with a wallet POST form and `ejecutar` submit but no table. Treating either state as a parser failure made the live surface unusable even though authentication was working.

Resolution: fixed and live-confirmed. The wallet reader now continues the own-name representation gate using the same safety rule as the auth driver: it accepts only AEAT's server-rendered own-name state and refuses representative mode. It also submits the wallet execute control only when the form action path matches the configured wallet path. The parser recognizes the exact authenticated empty-wallet shell as a zero-row, zero-pending wallet observation; arbitrary pages still raise `external_shape_changed`.

WALLET-026 | CRITICAL | Wallet page diagnostics exposed operator display text
While diagnosing the wallet page shape, an intermediate CLI-visible diagnostic included arbitrary button/body text. Live AEAT chrome can contain the active operator display name, so surfacing those fields is a private-information leak risk and must not be part of durable diagnostics or test output.

Resolution: fixed immediately after discovery. CLI-visible wallet shape diagnostics now include only structural fields needed for parser/navigation triage: landing URL, wallet-shell shape flag, heading/table/form counts, form id/name/method/action path, input id/name/type, and raw hash. Title text, headings, table headers, arbitrary button text, and body-text markers were removed; private wallet values were not hardcoded into code, tests, or vault notes.

WALLET-027 | HIGH | Review found the wallet execute POST and empty-wallet inference were under-guarded
The code-review pass found two high-risk issues after the first live success. First, the wallet execute control was a live POST performed under a read-only adapter, but the remote-state guard had only classified GET navigations. Second, the parser accepted the wallet shell as a zero balance based only on the wallet form shape, which could turn a pre-execute or failed-navigation page into a false zero wallet.

Resolution: fixed. `RemoteStateGuardPolicy` now has an explicit `allowed_read_post_paths` field. POST remains blocked by default, and only authenticated read surfaces may allow a declared path. The wallet policy declares only the configured `CarteraCuotas` path, and the wallet reader calls the guard before submitting the execute control. The parser now accepts the empty wallet shell only when the live reader passes `allow_empty_wallet_shell=True`, which is set only after the execute gate reports that it submitted. The standalone parser refuses the same shell by default.

WALLET-028 | MEDIUM | Review found broad auth landing acceptance and plaintext diagnostic context
The code-review pass also found that Cl@ve verification accepted any configured AEAT `/wlpl/` or `/Sede/` prefix, and wallet parse diagnostics still exposed text-bearing headings/table headers. The later live auth timeout also showed a full Cl@ve URL query in CLI-visible context.

Resolution: fixed. Cl@ve verification now accepts exact target URLs or same AEAT application paths, not arbitrary broad prefixes. Wallet parse diagnostics no longer include title text, headings, body text, button labels, or table headers; they report only structural counts, form/action/input shape, raw hash, and whether the wallet empty-shell shape was present. Cl@ve timeout contexts now include only URL host, path, and query-key names, not query values.

Verification after fixes:

- `uv run ruff check` passed for the wallet, recurrence, Modelo 303 guard, CLI, and repository files.
- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py -q --disable-warnings` completed with 38 passed and 1 live-gated deselected.
- `uv run pytest src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py -q --disable-warnings` completed with 13 passed after the final low test gap was closed.
- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/test_iva_wallet_live.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py -q --disable-warnings` completed with 42 passed and 2 live-gated deselected after adding the application-level live wallet test and removing scoped `monkeypatch` usage.
- `uv run pytest -m live_read src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/test_iva_wallet_live.py -q --disable-warnings -s` reached the live Cl@ve non-QR page and captured encrypted diagnostics, but did not complete authentication because operator approval did not complete within 120 seconds; a subsequent retry was blocked by AEAT's prior-pending-request refusal.
- `uv run pytest src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/test_iva_wallet_live.py -q --disable-warnings` completed with 20 passed and 2 live-gated deselected after the auth-driver fixes.
- A later background `uv run pytest -m live_read src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py -q --disable-warnings -s` run emitted a Cl@ve verification code, timed out after 120 seconds without AEAT post-auth redirect, captured encrypted diagnostic `20260520T142929Z`, and confirmed AEAT cancellation of the pending request. The wallet page was not read because auth did not complete.
- A diagnostic QR/headed run was performed with process-local overrides (`AEAT_CLAVE_PREFER_NON_QR=false`, `AEAT_BROWSER_HEADLESS=false`). It opened a visible QR Cl@ve page, timed out without post-auth redirect, captured encrypted diagnostic `20260520T143744Z`, and confirmed AEAT cancellation. This run confirms QR mode is implemented but does not confirm it is the expected/default operator flow.
- `uv run aeat config auth login --provider clave_movil` exercised the new live login surface and reached the non-QR Cl@ve wait page, but timed out after 120 seconds without AEAT post-auth redirect. It captured encrypted diagnostic `20260520T152302Z` with redacted mode/kind/headless/support-factor metadata. The wallet page was not read because auth did not complete.
- A subsequent `uv run aeat config auth login --provider clave_movil` retry reached the same non-QR Cl@ve wait page with verification code present, timed out after 120 seconds without AEAT post-auth redirect, and captured encrypted diagnostic `20260520T160230Z`. The diagnostic remains `phone_state=unknown` pending the operator's explicit report for that attempt.
- A later auth retry completed successfully after the operator approved the non-QR Cl@ve request. `uv run aeat config auth status --provider clave_movil` then reported `authenticated=True` and `available=True`.
- `uv run aeat app live iva-wallet capture-history --from-year 2024 --to-year 2024` completed with four captured observations and four reloaded secure history rows. `uv run aeat app live iva-wallet capture-history --from-year 2023 --to-year 2023` then completed with four additional observations and eight total reloaded secure history rows.
- A focused 2022 Modelo 303 filed capture persisted evidence but extracted zero casillas; focused 2023 and 2024 captures extracted casillas and promoted into calculation observations. This isolates an older artefact parser gap.
- `uv run aeat app live iva-wallet pull --year 2026 --period 2T` now reaches the wallet driver but AEAT redirects the direct wallet URL to `erro4033.html`; no wallet value was read or persisted. Online official-source research corrected the interpretation: AEAT documents Pre303 access with certificate/DNIe or Cl@ve PIN, so this is tracked as a driver route/selector gap rather than a certificate-only conclusion.
- `uv run pytest src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/core/test_external_constants.py src/aeat/application/auth/test_diagnostics.py src/aeat/entrypoints/cli/test_workflow_surface.py::test_config_auth_accepts_supported_provider_and_rejects_others -q --disable-warnings` completed with 46 passed.
- `uv run python -m aeat.locales audit` completed with all locale files ok after adding the new auth login and diagnostic report strings.
- `uv run ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py src/aeat/adapters/outbound/aeat/sede/__init__.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py` passed after externalizing the wallet/Pre303 constants.
- `uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py -q --disable-warnings` completed with 41 passed after the same constants pass.
- `uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/domain/portals -q --disable-warnings` completed with 99 passed after enrolling the Pre303 presentation-service and G313 constants.
- `uv run pytest src/aeat/core/test_external_constants.py src/aeat/domain/portals src/aeat/application/live/test_census_snapshot.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py -q --disable-warnings` completed with 147 passed after moving Sede-origin defaults, G313, and declarations read-guard host constants to the central registry.
- `uv run pytest src/aeat/core/test_external_constants.py src/aeat/domain/portals src/aeat/application/live/test_census_snapshot.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py -q --disable-warnings` completed with 162 passed after scrubbing exact route literals from production comments and keeping the values only in TOML.
- `uv run python -m aeat.locales audit` completed with `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok after removing the unused `application.setup.errors.workspace_bucket_torn` YAML key.
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/__init__.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/__init__.py` passed after retargeting wallet authentication to Pre303.
- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_iva_wallet_live.py -q --disable-warnings` completed with 5 passed and 1 live-gated deselected after the same change.

WALLET-029 | CRITICAL | Wallet driver attempted to pass through an AEAT execute form
The wallet navigation chain treated the `CarteraCuotas` execute form as part of the read route and attempted to submit `input#ejecutar`. This contradicted the ADR's permanent live-write prohibition and could turn a read-only wallet capture into an unapproved live AEAT form submission.

Resolution: fixed. The wallet driver now inspects the loaded HTML statically and raises a navigation error when the execute submit is present. It does not run page JavaScript for this inspection, does not click the submit control, and the wallet read guard no longer declares any allowed POST path. Added focused tests that reject POST to the wallet URL and detect the execute-submit shape as blocked.

WALLET-030 | CRITICAL | Empty wallet interpretation could mask a pre-execute shell
The parser could treat a no-table wallet page containing only the wallet form/execute shell as an empty wallet and return `total_pending=0`. That can convert an incomplete live route into false zero compensation evidence.

Resolution: fixed. The parser no longer accepts any no-table shell as an empty wallet. A captured wallet observation must contain a recognizable wallet table; otherwise parsing fails closed with external-shape context.

WALLET-031 | CRITICAL | Representation-gate auto-submit was hidden in live wallet/auth routing
The wallet route and Cl@ve verification path automatically continued AEAT's own-name representation gate. Even when it does not enter represented-party data, it is still a live AEAT form action and must not be hidden inside automated wallet capture or session verification.

Resolution: fixed for the reviewed wallet/Cl@ve path. Wallet capture now blocks when a representation gate appears. Cl@ve post-auth verification also fails closed instead of auto-submitting the representation form. Remaining live-auth clicks are limited to Cl@ve authentication flow controls and timeout cancellation of pending Cl@ve requests; those remain subject to separate auth-surface review.

WALLET-032 | HIGH | IVA wallet scope must expand into full IVA pipeline verification
The original wallet plan was scoped to Modelo 303 prior compensation authority. The broader backend risk is that ledger, periodic IVA forms, annual IVA summaries, cross-year carry-forward, and AEAT remote-state reconciliation can drift independently.

Resolution: scope expanded in the linked plan. Added a broader IVA calculation engine hardening wave covering ledger-to-form propagation, periodic and annual form verification, cross-year/multiyear state, AEAT remote reconciliation, and operator-persona CLI testimonial capture.
- `uv run aeat app live iva-wallet pull --year 2026 --period 2T` completed successfully after selector dispatch, representation-gate continuation, wallet execute handling, and empty-wallet parsing. It persisted an encrypted wallet observation, reloaded/reconciled it, selected AEAT wallet authority, reported zero wallet rows, and did not block the decision. No private wallet values were copied into this audit note.
- `uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/application/auth/_sessions.py src/aeat/application/wizard/_commands.py src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py` passed after the live wallet completion fixes.
- `uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/application/auth/test_ensure_session.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_iva_wallet_live.py -q --disable-warnings` completed with 60 passed and 1 live-gated deselected after the same fixes.
- `uv run pytest src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/application/live/test_iva_wallet_capture_backend.py -q --disable-warnings` completed with 73 passed after resolving the review findings.
- A strict live retry after resolving the review findings did not reach the wallet reader because Cl@ve authentication timed out after 120 seconds. That run emitted diagnostic `20260520T221522Z` with sanitized URL context. Therefore the stricter execute/empty-wallet rules are unit/integration verified, but they still need a fresh operator-approved live retry to reconfirm the wallet read.
- A 2026-05-21 live retry emitted verification code `X2A` and timed out before wallet navigation. It produced diagnostic `20260521T061613Z` with sanitized URL context. Operator phone-state testimony is pending, so no diagnostic report was recorded.
- The operator later reported that no approval prompt was received for that attempt. The phone-state report was recorded as `app_did_not_prompt`. A local configuration check confirmed the configured identity is a NIE matching the operator-supplied prefix; the full identifier was not copied into the audit note.
- Follow-up verification found that the diagnostic `show` projection still emitted stored URL query values. The diagnostic projection now redacts URLs to host/path plus query-key names, and `uv run aeat config auth diagnostics show 20260521T061613Z` renders the sanitized URL shape with the recorded phone state.

WALLET-033 | HIGH | Live browser actions were not explicit allow-list decisions
The W02.P02 inventory found that several live AEAT browser actions were still effectively allowed by absence of forbidden words: declarations register clicks, wallet Cl@ve selector dispatch, and CSV verification form entry used the remote-state guard but did not require an explicit read-only action classification. This meant a new unreviewed click label could pass as long as it did not contain a canonical write token.

Resolution: fixed for the wallet/declarations/CSV/oracle/live-consult surfaces. `RemoteStateGuardPolicy` now supports `allowed_browser_action_patterns`; policies that declare this field reject unclassified browser actions. Wallet, declarations, declarations snapshot-derived read policies, CSV verification, GROI/NIF-IVA oracle policies, Renta WEB Open oracle policies, and the direct GROI/NIF-IVA live drivers now source accepted action markers from `external_constants.toml`. Tests prove unknown action labels are blocked and wildcard-reviewed labels resolve through the guard. Auth cleanup remains classified as authentication-only/diagnostic cleanup rather than tax-surface submission, and walker-style DOM expansion remains read-only navigation without form-submit controls.

WALLET-034 | HIGH | Renta WEB Open planned operations omitted runtime casilla navigation
The live Renta WEB Open driver could navigate to casillas, fill override values, return to Resumen, and scrape extra casillas, but its `planned_operations` only declared the initial simulator startup, profile fill, summary scrape, and context close. That made remote-state preflight incomplete for exactly the runtime steps that touch form widgets.

Resolution: fixed. `RentaWebOpenSedeDriver.planned_operations` now emits `navigate-to-casilla:*`, `apply-casilla-override:*`, `navigate-to-resumen`, and extra scrape-casilla navigation actions from the live payload. Those action patterns are centralized in `external_constants.toml`, and focused tests prove the planned list includes override/scrape navigation and rejects unclassified Renta actions.

WALLET-035 | CRITICAL | Live Cl@ve auth could bind the wrong taxpayer identity to the active profile
The active profile was initially `roger-design`, while the configured Cl@ve Móvil identity matched a different live profile, `live-operator-active`. `aeat config auth configure --provider clave_movil` reported `identity_alignment=mismatch`, but the central live-auth session path did not itself fail closed before attempting a live wallet read. This could persist AEAT observations for one taxpayer into another active profile if the operator missed the warning.

Resolution: fixed. The active profile was switched to `live-operator-active`, Cl@ve auth was configured there, and the configure/status surface now reports `identity_alignment=matches` and `configured=True` for that profile. The central `ensure_authenticated_aeat_session` / `require_verified_aeat_session` path now requires Cl@ve's configured identity to match the active profile `identity.tax_id` before reusing or creating a live AEAT session, and also rejects a reused session whose identity differs from the expected profile identity. The refusal exposes no tax identifier values. The Cl@ve timeout suggestion now names the exact `aeat config auth diagnostics report DIAGNOSTIC_ID --phone-state ...` command shape.

Verification:

- `uv run aeat config profile switch live-operator-active` completed.
- `uv run aeat config auth configure --provider clave_movil; uv run aeat config auth status --provider clave_movil` completed with active profile `36732be3-652a-4400-92b8-dcaf39e1e0a0`, `identity_alignment=matches`, `configured=True`, and `available=True`.
- `uv run aeat app live iva-wallet pull --year 2026 --period 2T` reached the non-QR Cl@ve wait page and emitted verification code `DHM`, then timed out after 120 seconds without AEAT completing the browser-side redirect. It produced diagnostic `20260521T064750Z`; no wallet data was read or persisted in this retry.
- `uv run ruff check src/aeat/application/auth/_sessions.py src/aeat/application/auth/__init__.py src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_ensure_session.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/core/errors/registry/_application.py` passed.
- `uv run pytest src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_ensure_session.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -q --disable-warnings` completed with 44 passed.

WALLET-036 | HIGH | Transaction-backed IVA projection could not represent non-domestic and adjustment IVA facts
The W03.P01 ledger audit found that the transaction-backed IVA aggregator could only manufacture domestic IVA observations from `iva_rate` plus ledger direction. The domain and registry already model recargo de equivalencia, exenciones, intra-community reverse charge, imports/exports, OSS/IOSS, and signed corrections, but the generic periodic IVA input path had no pre-classified hand-off for those axes. That could silently leave whole IVA categories outside Modelo 303/309/390 binding resolution, while tests still passed for ordinary domestic IVA.

Resolution: fixed for the generic IVA aggregation boundary. Added a pre-classified `IvaLedgerCandidate` path that requires upstream category, rate kind, flow direction, signed base, signed cuota, and an explicit ordinary-vs-adjustment input kind before creating registry-ready `IvaLedgerObservation` rows. The legacy transaction projection remains restricted to domestic-rate inference. OSS/IOSS remains on the existing Modelo 369-specific candidate path. New tests cover exempt, recargo de equivalencia, intra-community reverse charge, signed adjustment rows, Modelo 309 binding resolution through real registry selectors, sentinel-category rejection, and outside-period blocking.

Verification:

- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/test_oss_ioss.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 58 passed.
- `uv run ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py` passed.
- `git diff --check -- src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py` passed.

WALLET-037 | MEDIUM | Modelo 303 bucket aggregation tests did not prove registry formula provenance
The W03.P01.S02 audit found that the bucket aggregation integration test verified ledger-derived bound values reached Modelo 303, but did not assert that the persisted revision retained bound-casilla legal/source provenance and computed-casilla formula provenance from the registry engine. That left a regression path where application code could keep numeric outputs while losing the evidence chain required by the calculation-grounding rules.

Resolution: fixed. The Modelo 303 bucket aggregation test now asserts that bound ledger casillas are persisted as non-formula `CasillaObservation` rows with legal/source refs, and that computed result casillas carry the expected registry formula id, operand refs, legal refs, and source refs. The assertion is structural and provenance-based; it does not reimplement Modelo 303 arithmetic in the test.

Verification:

- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 4 passed.
- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 35 passed.
- `uv run ruff check src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py` passed.
- `git diff --check -- src/aeat/application/modelo/test_bucket_aggregation_flow.py` passed.

WALLET-038 | MEDIUM | Modelo 303 trace tests did not span positive, negative, zero, and compensation-applied periods
The W03.P01.S03 audit found that Modelo 303 bucket aggregation had a single ordinary positive-period integration scenario plus separate wallet-decision tests. It did not exercise the full period-outcome shape from ledger rows through Modelo 303 outputs: positive result, negative result with generated compensation, exact zero, and a positive period reduced by a persisted non-blocking compensation decision.

Resolution: fixed. Added a bucket-aggregation trace test that seeds real ledger rows across four quarterly periods, calculates each period through `calculate_modelo_revision_from_bucket_aggregation`, verifies bound and computed casilla provenance for every revision, and asserts the output signs/state transitions for positive, negative, zero, and compensation-applied periods. The compensation-applied scenario keeps the Modelo 303 wallet-decision guard active by using a matching profile identity and non-blocking decision.

Verification:

- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 5 passed.
- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 59 passed.
- `uv run ruff check src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py` passed.
- `git diff --check -- src/aeat/application/modelo/test_bucket_aggregation_flow.py` passed.

WALLET-036 | HIGH | Auth diagnostics did not carry enough configuration context to explain missing phone prompts
The operator reported no Cl@ve phone prompt for diagnostic `20260521T064750Z` and correctly noted that the diagnostic did not make it easy to cross-reference the auth request with the active profile, Cl@ve identity/support factors, or certificate state. Without that configuration snapshot, a no-prompt timeout can be misdiagnosed as an AEAT/browser failure when it may be profile/identity configuration drift.

Resolution: fixed for new diagnostics. Cl@ve auth diagnostics now persist an operator-safe attempt snapshot: active profile id/label, profile registration and profile-record presence, profile tax-id presence, identity alignment, Cl@ve identity kind/configured flag, DNI date/NIE support-factor presence, non-QR/headless/timeout settings, certificate path/password/file/backend state, and short SHA-256 fingerprints for profile tax id, Cl@ve identity, contrast factors, and certificate path. Raw NIE, support number, dates, and certificate paths are not emitted. The diagnostics CLI `list` now shows profile and alignment columns; `show` renders the full redacted snapshot.

Verification:

- `uv run aeat config auth diagnostics report 20260521T064750Z --phone-state app_did_not_prompt` recorded the operator testimony for the last timeout.
- `uv run aeat config auth diagnostics show 20260521T064750Z` shows the recorded phone state. The profile snapshot fields are blank for that older diagnostic because it predates this fix.
- A direct diagnostic-context probe against the current active profile reported profile `live-operator-active`, `identity_alignment=matches`, profile record/tax-id present, NIE support configured, and no certificate configured; only booleans and fingerprints were printed.
- A fresh live wallet retry emitted verification code `35X`, timed out after 120 seconds, and produced diagnostic `20260521T071445Z`. The diagnostic now shows active profile `live-operator-active`, `identity_alignment=matches`, matching profile/Cl@ve identity fingerprints, NIE support configured, and no certificate configured. Phone-state testimony for this newest attempt remains pending.
- `uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py src/aeat/entrypoints/cli/_config/__init__.py` passed.
- `uv run pytest src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_ensure_session.py src/aeat/application/auth/test_diagnostics.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -q --disable-warnings` completed with 45 passed.

WALLET-039 | MEDIUM | Modelo 390 annual compensation reconciliation did not prove casillas 97/662 from four Modelo 303 periods
The W03.P02.S01 audit found that the Modelo 390 registry path already declared annual ledger bindings and previous-filing bindings, but the cross-period test did not drive negative quarterly Modelo 303 results that populate annual compensation casillas `97` and `662`. That left a gap where the main annual total reconciliation could pass while the wallet-sensitive annual carry-forward fields were unproven.

Resolution: fixed. The Modelo 390 annual IVA pipeline test now calculates four Modelo 303 periods from ledger observations, including negative periods that generate compensation, then calculates the Modelo 390 annual snapshot from both annual ledger observations and the generated quarterly 303 observations. The test asserts annual ledger totals reconcile with 303-sourced annual totals, casilla `97` equals the fourth-quarter available compensation observation, and casilla `662` equals the non-fourth-quarter generated compensation observations. Expected compensation values are read from the produced 303 observations rather than hard-coded from a duplicated Modelo 390 formula.

Verification:

- `uv run pytest src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 18 passed.
- `uv run pytest src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/core/test_external_constants.py -q` completed with 55 passed.
- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 5 passed after adjusting assertions to distinguish work-unit creation events from calculation-created events.
- `uv run ruff check src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/core/test_external_constants.py` passed.
- `git diff --check -- src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/core/test_external_constants.py` passed.

WALLET-040 | HIGH | Pre-classified unsupported IVA regimes could be silently dropped from Modelo 390 annual binding resolution
The W03.P02.S02 audit found that `resolve_ledger_iva_aggregation_binding_values` correctly returns zero for empty match sets, but the same behavior was unsafe for concrete pre-classified IVA observations whose category/rate/flow triple is not selected by any Modelo 390 annual binding. Regimes represented in the IVA catalogue, such as recargo de equivalencia or other non-ordinary categories, could be passed to a Modelo 390 candidate-binding call and disappear as a zero contribution instead of surfacing as a modelling gap.

Resolution: fixed. The registry now exposes `unsupported_ledger_iva_observations`, which identifies concrete IVA ledger observations no `ledger_iva_aggregation` selector on a revision can consume. The pre-classified candidate binding path calls this before resolving binding values and fails closed with `unsupported_iva_category` context when the target modelo cannot consume an observation. Modelo 309 recargo/reverse-charge support remains verified through its own bindings; Modelo 390 now blocks unsupported recargo candidates instead of inferring or dropping them.

Verification:

- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 43 passed.
- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 60 passed.
- `uv run ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py` passed.
- `git diff --check -- src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py` passed.

WALLET-041 | MEDIUM | Cross-form Modelo 390 tests did not exercise the application observation-store prefill path
The W03.P02.S03 audit found that registry-level 390/303 reconciliation coverage existed, but the application path that reads persisted 303 observations from the encrypted local observation store and uses them to prefill Modelo 390 previous-filing bindings was not covered by a cross-form annual calculation test. A regression in observation persistence, lookup, or binding-prefill provenance could therefore break annual reconciliation while registry-only tests still passed.

Resolution: fixed. Added an application-level binding-prefill test that calculates four Modelo 303 periods from ledger observations, persists the resulting typed 303 observations in `CalculationObservationRepository`, resolves Modelo 390 previous-filing bindings from that store, and calculates the annual Modelo 390 snapshot from annual ledger bindings plus local-store prefill values. The test compares annual totals to 303-sourced reconciliation casillas through production registry outputs and does not duplicate Modelo 303 or Modelo 390 formulas in test code.

Verification:

- `uv run pytest src/aeat/application/calculations/test_binding_prefill.py -q` completed with 1 passed.
- `uv run pytest src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py -q` completed with 36 passed.
- `uv run ruff check src/aeat/application/calculations/test_binding_prefill.py` passed.
- `git diff --check -- src/aeat/application/calculations/test_binding_prefill.py` passed.

WALLET-042 | HIGH | IVA compensation history lacked source-period carry-forward lots
The W03.P03.S01 audit found that the secure Modelo 303 compensation history persisted latest per-period amounts, but did not model carry-forward lots by source period. Without source-year/source-period lots, the application could compare aggregate wallet/local balances but could not explain age, applied amount, remaining amount, or expiry-review state across fiscal years.

Resolution: fixed for the modelling layer. Added `IvaCompensationCarryForwardLot`, `IvaCompensationCarryForwardReport`, and `IvaCompensationExpiryReviewState`, plus `build_iva_compensation_carry_forward_report`. Filed-period generated amounts now project into source-period lots, applied amounts consume earlier lots FIFO, remaining balances are preserved, unallocated applications are surfaced, and each lot carries age and expiry-review state. This step models review state only; hard four-year enforcement is reserved for the next policy step.

Verification:

- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py -q` completed with 4 passed.
- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q` completed with 17 passed.
- `uv run ruff check src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.
- `git diff --check -- src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.

WALLET-043 | HIGH | Four-year IVA compensation policy was not enforceable from source-dated lots
The W03.P03.S02 audit found that after source-period carry-forward lots were modelled, the application still needed an explicit policy gate that refuses remaining compensation balances outside the LIVA art. 99 four-year window. Without that gate, a same-year aggregate recurrence could still hide an expired source-period balance.

Resolution: fixed for the policy boundary. Added `IvaCompensationCarryForwardPolicyError` and `enforce_iva_compensation_four_year_window`, which refuses any carry-forward lot with remaining amount and `expired_review_required` state. Fully applied expired lots are allowed because no remaining balance can be applied. The gate uses each lot's source filing year and source period, not an aggregate recurrence amount.

Verification:

- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py -q` completed with 6 passed.
- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q` completed with 19 passed.
- `uv run ruff check src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.
- `git diff --check -- src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.

WALLET-044 | MEDIUM | Multiyear IVA compensation tests did not tie carry-forward lots to wallet reconciliation outcomes
The W03.P03.S03 audit found that generation/application/expiry tests and wallet divergence tests existed as separate surfaces, but there was no single multiyear scenario proving that a source-period carry-forward lot can feed the reconciliation decision with wallet divergence and local filed-history fallback behavior.

Resolution: fixed. Added a multiyear compensation-flow test that creates a generated balance in one fiscal year, applies part of it in a later year, verifies the expiry-boundary review state and remaining local balance, then feeds that dated local balance into wallet reconciliation. A higher AEAT wallet amount blocks automatic output, while a missing wallet falls back to the local filed-history recurrence amount.

Verification:

- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q` completed with 20 passed.
- `uv run ruff check src/aeat/application/calculations/test_iva_compensation_history.py` passed.
- `git diff --check -- src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.

WALLET-040 | CRITICAL | Representation-gate continuation needed a narrower own-name safety model
The 2026-05-21 live retry emitted Cl@ve verification code `KLS` and, after operator-side approval, reached AEAT's representation gate. That proves the latest blocker was no longer missing Cl@ve delivery. However, selecting/submitting the representation gate would send a live form action to AEAT, which violates the current hard mandate: automated drivers may pull read-only information from AEAT/Sede, but must not send live taxpayer information or live form choices to AEAT.

Resolution: fixed as a narrower own-name allowance. Follow-up analysis distinguished the acting-capacity selector from a filing or represented-third-party submission. The Cl@ve post-auth path and wallet driver may now continue only through AEAT's configured `representation_own_name_selector` for the authenticated profile user, followed by the configured representation continue button. The allowed browser action is centrally declared as `representation-gate-own-name-continue`. The driver does not fill represented-party NIF/name fields, does not select representative mode, and still fails closed if the own-name selector is unavailable or the gate shape is unknown.

Verification:

- `uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py -q --disable-warnings` completed with 63 passed.
- `uv run ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py` passed.
- `git diff --check -- src/aeat/core/external_constants.py src/aeat/core/external_constants.toml src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py` passed.

WALLET-041 | HIGH | Current auth/wallet tests embedded AEAT Sede constants outside the settings schema
Focused auth/wallet protocol tests still embedded AEAT origins, Cl@ve Móvil paths, Sede representation paths, wallet paths, and selectors directly in test doubles. That weakens the central settings/schema contract because tests can keep passing after the TOML-backed external constants drift from the driver assumptions.

Resolution: fixed for the auth/wallet live surface touched in this pass. Added the missing AEAT `www12` origin and Cl@ve Móvil path constants to `external_constants.toml` and the typed schema: representation dialog path, QR path, non-QR path, DNI/NIE contrast path, and cancellation path. The Cl@ve Móvil protocol test doubles and IVA wallet tests now derive AEAT origins, paths, and selectors from `Settings.external_constants()` or exported canonical URLs. A focused literal scan of the touched auth/wallet files now finds no hardcoded AEAT URL/path/selector literals outside the TOML-backed registry; the remaining match is a JavaScript page property name used inside Cl@ve browser evaluation.

Open follow-up: broader repository tests still contain older hardcoded AEAT URLs and host allow-lists outside this focused surface. They are in scope for a separate centralisation cleanup and must not be used as proof that hardcoding is acceptable.

WALLET-045 | HIGH | Direct Modelo 303 calculation calls could apply unpersisted IVA wallet decisions
The W03.P04.S01 audit found that `calculate_modelo_revision` and the bucket-aggregation wrapper accepted an in-memory `iva_compensation_decision` object. The lower guard validated taxpayer, period, blocked state, and conflicts, but did not prove that the decision had been written to the encrypted IVA wallet decision repository. A caller could therefore make a remote-state-derived value affect Modelo 303 output without leaving the required persisted reconciliation record.

Resolution: fixed. Modelo 303 calculation now reloads the persisted decision for the work unit and refuses a supplied decision unless it exactly matches the encrypted latest decision for the taxpayer/year/period. When no decision is supplied, the existing persisted replay path remains the only authority. The bucket-aggregation wrapper carries an injectable real `IvaWalletDecisionRepository` so repository-backed tests and bucket-local secure SQL stores can share the same persisted decision without fakes or monkeypatching.

Verification:

- `uv run pytest src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py -q` completed with 19 passed.
- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py` passed.

WALLET-046 | HIGH | IVA wallet decisions did not carry structured authority-source provenance
The W03.P04.S02 audit found that reconciliation decisions kept separate amount fields for AEAT wallet, local recurrence, and taxpayer override, but did not persist a structured source list. That made it harder for downstream audit and operator surfaces to distinguish the live AEAT wallet capture, the derived local recurrence value, the filed-history observations that produced the recurrence, and explicit taxpayer override evidence.

Resolution: fixed. Added `IvaCompensationAuthoritySource` and `authority_sources` to `IvaCompensationReconciliationDecision`. Reconciliation now records AEAT wallet evidence, local recurrence evidence, filed-history observation provenance, and taxpayer override evidence as separate source records. The application reconciliation path converts the local Modelo 303 recurrence into both a `local_recurrence` source and a distinct `filed_history_observation` source with source modelo, filing year, source periods, and resolution time.

Verification:

- `uv run pytest src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q` completed with 18 passed.
- `uv run ruff check src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py` passed.
- `git diff --check -- src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_bucket_aggregation_flow.py .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md .vault/audit/2026-05-20-live-iva-compensation-wallet-review.md .vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p04-s01.md` passed with CRLF warnings only.

WALLET-047 | HIGH | Verified Modelo 303 revisions could be exported after a later blocked wallet decision
The W03.P04.S03 audit found that calculation already refused blocked IVA wallet decisions, but a previously verified Modelo 303 revision could still be exported if a newer persisted reconciliation decision later became blocked. That creates a stale-output risk: export is local-only and does not contact AEAT, but it produces the file an operator could manually present, so it must observe the latest blocked remote-state reconciliation.

Resolution: fixed. Verification now adds a blocking finding when the latest persisted Modelo 303 wallet decision is blocked. Export now checks the addressed work unit's latest persisted wallet decision before building any draft or writing any file, and raises `ModeloIvaWalletReconciliationBlocked` when the decision is blocked. The CLI export verb catches and renders that refusal as an operator-visible bad-parameter message.

Verification:

- `uv run pytest src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py -q` completed with 19 passed.
- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py src/aeat/entrypoints/cli/_modelo.py` passed.
- `git diff --check -- src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py src/aeat/entrypoints/cli/_modelo.py src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md .vault/audit/2026-05-20-live-iva-compensation-wallet-review.md .vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p04-s01.md .vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p04-s02.md` passed with CRLF warnings only.

WALLET-048 | HIGH | Modelo 303 readiness can report ready while ledger preflight blocks the same period
The W04.P02 persona dry-run found that `uv run aeat app ledger preflight --period 2026Q1` reported `ready false` for a business ledger transaction missing `category_id`, but `uv run aeat app modelo readiness --modelo 303 --revision-id 2009-y-siguientes --year 2026 --period 1T` reported `ready True`. A subsequent Modelo 303 calculation emitted a zero-valued draft even though the ledger contained an incomplete business transaction in the same period. This can mislead an operator into trusting an unsafe zero calculation.

Required follow-up: Modelo readiness and/or calculate-from-ledger paths must incorporate ledger preflight/readiness for ledger-owned Modelo 303 bindings. A period with incomplete or unclassified ledger evidence should not report ready, and calculation should not silently reuse or emit a zero draft when ledger preflight blocks the period.

WALLET-049 | MEDIUM | CLI ledger diagnostics hide tax fields needed to understand IVA aggregation readiness
The W04.P02 persona dry-run found that `ledger view` for a transaction showed id, date, amount, description, and review status, but not the tax fields that determine Modelo 303 aggregation: category, taxable base, IVA rate, IVA amount, and classification readiness. Operators must jump between `ledger categories`, `ledger preflight`, and calculation output to infer why a ledger row was ignored.

Required follow-up: ledger view/status output should surface tax-relevant fields and readiness state for calculation diagnostics.

WALLET-049-RESOLUTION | MEDIUM | Fixed ledger status tax diagnostics for IVA readiness
Resolution: fixed. `ledger view` already renders the stored category, taxable base, IVA rate, IVA amount, and classification fields. `ledger status --period` now also emits one `readiness_issue` line per preflight issue, including transaction id, business classification, category id, taxable base, IVA rate, IVA amount, issue reason, and issue detail. This lets an operator understand the IVA calculation blocker from the status surface without re-entering individual transaction views.

Verification:

- `uv run pytest src/aeat/entrypoints/cli/test_ledger_preflight_verb.py::test_status_period_readiness_issues_include_tax_diagnostic_fields src/aeat/entrypoints/cli/test_ledger_preflight_verb.py::test_preflight_empty_catalogue_is_ready -q` completed with 2 passed.
- `uv run ruff check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_ledger_preflight_verb.py` passed.

WALLET-050 | HIGH | CLI does not yet expose IVA compensation carry-forward lots or authority-source decisions
The W04.P02 multiyear persona found that `iva-wallet history` help names secure local compensation history, but an empty command only returns `row_count=0`, and available Modelo 303 binding output shows only that prior compensation is a `previous_filing` binding. The CLI does not yet expose source-year/source-period lots, age, remaining amount, expiry review state, or persisted wallet/local/override authority-source decisions.

Required follow-up: add CLI output for carry-forward lots and persisted IVA wallet authority-source decisions before asking operators to validate multiyear compensation.

WALLET-050-RESOLUTION | HIGH | Fixed carry-forward lots and authority decisions in IVA wallet history output
Resolution: fixed. `list_iva_compensation_history` now projects secure Modelo 303 period states through the existing IVA carry-forward engine and returns source-year/source-period lots, generated/applied/remaining amounts, age, expiry review state, and unallocated applied amount. It also lists persisted latest IVA wallet reconciliation decisions from the encrypted decision repository, including selected authority, wallet/local/override amounts, divergence, blocked/stale flags, and structured authority-source summaries. `aeat app live iva-wallet history` renders those rows and adds `--as-of-year` so operators can inspect expiry state for a specific fiscal year without contacting AEAT.

Verification:

- `uv run pytest src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_history_output_lines_surface_lots_and_authority_decisions src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy -q` completed with 4 passed.
- `uv run ruff check src/aeat/application/calculations/_observations_repository.py src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_registry_cli.py` passed.

WALLET-052 | HIGH | Fixed live IVA wallet CLI no-submit safety surfacing
Resolution: fixed. `aeat app live iva-wallet` help now names the read-only fail-closed policy before representation choices or wallet form submission. `iva-wallet pull` help states that no AEAT wallet forms are submitted and that representation gates only continue in own-name mode. `iva-wallet capture-history` help states that no AEAT filing or wallet form choices are submitted. Successful `iva-wallet pull` and `capture-history` text output includes explicit safety metrics for read-only fail-closed behavior, own-name-only representation gates, and no wallet/representation choices posted.

Verification:

- `uv run pytest src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_pull_output_lines_name_no_submit_policy src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_iva_history_cli_requires_live_gate_before_local_writes -q` completed with 3 passed.
- `uv run pytest src/aeat/locales/test_locale_translation_honesty.py src/aeat/application/wizard/test_wizard_translations_resolve.py -q` completed with 5 passed.
- `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_registry_cli.py` passed.

WALLET-051 | MEDIUM | Review found verify/export blocked-wallet guards need decision-repository injection
The W04.P02.S03 code review found that `calculate_modelo_revision` can validate supplied wallet decisions against an injected `IvaWalletDecisionRepository`, but verification and export currently load blocked wallet decisions through the default repository. Production default settings remain covered, but service callers using injected secure SQL repositories cannot inject the matching wallet-decision repository into verify/export, which weakens the new safety gate's testability and consistency.

Required follow-up: add `iva_compensation_decision_repository` injection to `verify_modelo_revision` and `export_modelo_revision`, then cover both with real secure SQL-backed tests.

WALLET-051-RESOLUTION | MEDIUM | Fixed repository-injected blocked-wallet guards for Modelo verify/file/export
Resolution: fixed. `verify_modelo_revision`, `file_modelo_revision`, and `export_modelo_revision` now accept the caller's `IvaWalletDecisionRepository` and use it for persisted blocked-wallet decisions before verified-state, filing-state, or export-file mutations. The file guard was included because an already verified Modelo 303 revision can otherwise reach internal filing after a later blocked wallet decision.

Verification:

- `uv run pytest src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py -q` completed with 13 passed.
- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py` passed.
- `git diff --check -- src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py` passed.

WALLET-048-RESOLUTION | HIGH | Fixed Modelo 303 readiness/calculation divergence from ledger preflight
Resolution: fixed. `build_operator_state_projection` now folds real ledger preflight into Modelo readiness for revisions with ledger-owned bindings. The Modelo readiness CLI renders `profile_ready`, `ledger_preflight_required`, `ledger_ready`, `ledger_period`, checked transaction count, and individual ledger issues. Ledger-backed Modelo calculation now runs the same preflight before evaluating the registry and refuses when active period ledger rows have blocking readiness issues, preventing the unsafe zero-draft outcome observed by the persona dry-run.

Verification:

- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/test_state_projection.py::test_modelo_303_readiness_includes_ledger_preflight_blockers -q` completed with 7 passed.
- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/test_state_projection.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_export.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py -q` completed with 34 passed.
- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/state_projection.py src/aeat/application/test_state_projection.py src/aeat/entrypoints/cli/_modelo.py` passed.
- Disposable CLI probe showed `ready False`, `ledger_ready False`, and `ledger_issue ... missing_category ...`; `aeat app modelo work calculate` refused with `ledger preflight blocks modelo calculation`.

WALLET-053 | MEDIUM | Older executable Sede/auth routes still needed centralisation guard coverage
The WALLET-041 follow-up scan found that the focused auth/wallet surface was clean, but adjacent executable live Sede code still contained centralized-route debt: the CSV verifier pinned the Sede host directly in its read guard, declarations register navigation validated the final URL with an embedded path fragment, and expediente parsing embedded cotejo and IRPF route regex fragments instead of deriving them from `external_constants.toml`. These were read-only surfaces, not live submission paths, but they weakened the external-constants contract for audited AEAT-owned route drift.

Resolution: fixed. The CSV verifier read guard now derives its allowed host from `aeat.domains.sede`. The declarations register final-URL check derives its path prefix from `aeat.sede_paths.declarations_listing`. The expediente parser derives cotejo CSV matching from `aeat.sede_paths.cotejo_query`, and the IRPF detail year route now lives in the typed `aeat.sede_paths` registry as prefix/suffix constants. A structural AST guard now scans the live auth/Sede/wallet/CSV executable modules and fails if AEAT host, `/wlpl/`, `/Sede/`, selector-access, or wallet route literals appear outside docstrings.

Verification:

- `uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/verify/test_verify.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestExtractCsvFromUrl src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestReadOperationGuard src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -q --disable-warnings` completed with 91 passed.
- `uv run pytest src/aeat/core/test_external_constants.py::test_live_sede_executable_route_literals_stay_centralized -q --disable-warnings` completed with 1 passed.
- `uv run ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/verify/__init__.py src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/_parse.py` passed.
- `git diff --check -- src/aeat/core/external_constants.toml src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/verify/__init__.py src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/_parse.py` passed.

WALLET-054 | CRITICAL | Reconfirmed live wallet read-query policy and corrected stale no-submit wording
On 2026-05-21, a live Cl@ve-approved wallet pull reached the authenticated `CarteraCuotas` surface through the Pre303 selector route and own-name representation gate. The first pass exposed a regression in the wallet execute handling: the driver treated the pre-execute wallet shell as a parser failure because the execute-read result was not propagated into the parser. The CLI also still claimed that no wallet form action was used, which was inaccurate after the guarded authenticated read-query policy.

Resolution: fixed and live-confirmed. The wallet reader now waits for the configured `wallet_execute_submit_selector`, guards the configured wallet read POST path through `RemoteStateGuardPolicy.allowed_read_post_paths`, performs only the centrally allowed `wallet-execute-read-query` browser action, and passes that result into `parse_iva_compensation_wallet_html(..., allow_empty_wallet_shell=True)`. The standalone parser still refuses the same shell by default. CLI help and metrics now say `wallet_execute_read_query_only_no_filing_or_represented_taxpayer_data`, so the operator-facing contract no longer implies that no wallet read-query POST occurred. No filing, payment, declaration submission, represented-taxpayer data entry, or taxpayer amount was sent or copied into this note.

Live verification:

- `uv run aeat app live iva-wallet pull --year 2026 --period 2T` completed after Cl@ve approval and persisted encrypted wallet evidence. The result selected `aeat_wallet`, reported zero wallet rows, and was not blocked. Private identity and observation keys remain represented only by hashes/secure-object paths.
- A follow-up run after the CLI wording fix emitted `aeat_form_submission_policy=wallet_execute_read_query_only_no_filing_or_represented_taxpayer_data` and again completed without stderr.

Focused verification:

- `uv run pytest src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_pull_output_lines_name_guarded_read_query_policy src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/core/test_external_constants.py -q --disable-warnings` completed with 41 passed.
- `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_registry_cli.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/core/test_external_constants.py` passed.
- `uv run python -m aeat.locales audit` reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok.

WALLET-055 | HIGH | Tightened empty-wallet interpretation after guarded read query
The W04 continuation review found that the parser could still accept a no-table wallet page as zero compensation when `allow_empty_wallet_shell=True`, even if the page still exposed AEAT's executable `ejecutar` submit control. That shape is ambiguous: it can mean the read query did not actually produce a result page, so accepting it as `total_pending=0` risks converting an incomplete live read into false remote-state evidence.

Resolution: fixed offline. The parser now only accepts an authorized empty wallet shape when the configured wallet form is present but the execute submit control is absent. The live read-query driver also re-inspects the page after clicking the guarded wallet execute control and raises `external_shape_changed` if the post-query page still exposes the execute control without a recognizable wallet table. This pass did not contact AEAT.

Verification:

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py -q --disable-warnings` completed with 13 passed.
- `uv run pytest src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_pull_output_lines_name_guarded_read_query_policy src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy src/aeat/core/test_external_constants.py::test_live_sede_executable_route_literals_stay_centralized src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py -q --disable-warnings` completed with 16 passed.
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py` passed.

WALLET-056 | MEDIUM | Safety plan wording still implied an absolute no-form policy
After the W054 policy correction, the implementation and CLI correctly distinguish prohibited AEAT filing/payment/represented-taxpayer submissions from the centrally guarded wallet read-query POST. The plan text still used absolute "no AEAT form" language in the W02 wave and live-wallet persona brief. That drift could mislead later work into either weakening the current fail-closed guard model or reintroducing inaccurate operator-facing no-form claims.

Resolution: fixed as vault plan hygiene. The W02 intent now states the prohibited classes of AEAT form submission and names the single guarded `CarteraCuotas` read-query exception. The W02.P01 phase text requires any read-query exception to be explicit in the remote-state guard and parser fail-closed tests. The W04 live-wallet persona row now asks reviewers to verify no filing/payment/represented-taxpayer choice is submitted beyond the guarded wallet read query.

Verification:

- `uv run vaultspec-core vault plan status .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md` completed with 44 of 44 steps complete.
- `uv run vaultspec-core vault check frontmatter --feature live-iva-compensation-wallet` reported clean.
- `uv run vaultspec-core vault check links --feature live-iva-compensation-wallet` reported clean.

WALLET-057 | HIGH | Live IVA process degradation is now tracked as its own plan wave
The 2026-06-04 live read work exposed process-degradation failures that are separate from IVA arithmetic correctness: a live capture attempt exceeded the outer tool timeout and required exact-match cleanup of stale `capture-remote-state` child processes, and the required `vaultspec-rag` semantic search path failed with `local_store_locked` because the local Qdrant store was already in use. These are production-readiness failures, not acceptable operator behavior.

Required follow-up: execute `W10.P24.S92`, `W10.P24.S93`, and `W10.P24.S98` in the live IVA wallet plan. The work must add process-level watchdog/stale-child assertions for live read CLI commands, repeat read-only live capture with before/after stale-process checks and only redacted aggregate evidence, and make RAG discovery lock-safe or at least typed/diagnostic instead of silently blocking required audit search.

WALLET-058 | CRITICAL | AEAT_LIVE_TESTS_ENABLED is conflated with operational live CLI access
The live IVA retry showed the operator-facing read path can be blocked before AEAT contact by the test opt-in variable: `AEAT_LIVE_TESTS_ENABLED=true` was rejected because the current gate requires literal `1`. The follow-up `rg`/`fd` inventory also shows production-facing live read surfaces still document or call the same `AEAT_LIVE_TESTS_ENABLED` access gate used by pytest live tests. That is a behavioral design bug: the variable name is test-scoped, and operator CLI live read access must be controlled by profile readiness, authentication configuration, remote-state read-only guards, and permanent no-submit gates, not by a pytest opt-in.

Required follow-up: execute `W11.P25.S94` through `W11.P25.S97` in the live IVA wallet plan. `AEAT_LIVE_TESTS_ENABLED` must remain a pytest/live-test marker concern only; operational live read CLI paths must be audited and reworked without weakening read-only/no-submit safety.

2026-06-04 partial resolution: `W11.P25.S95` reworked the central `AeatAccessGate` so `AEAT_LIVE_TESTS_ENABLED` is required only when a live read executes under pytest. Normal operator live reads now continue to the existing auth/profile/read-only guards without being blocked by the test opt-in value. `login_operator_auth` routes through the central gate and translates the typed pytest-only refusal for UI purposes. Focused tests prove non-pytest operator context is admitted, pytest context still refuses without literal `1`, and legacy pytest CLI live-gate ordering still refuses before local writes. `W11.P25.S94`, `W11.P25.S96`, and `W11.P25.S97` remain open for the full inventory, marker taxonomy, and static guard.

2026-06-04 static-guard follow-up: `W11.P25.S97` added a marker-integrity guard that scans production Python modules under `src/aeat/adapters`, `src/aeat/application`, `src/aeat/core`, and `src/aeat/entrypoints` and refuses any `AEAT_LIVE_TESTS_ENABLED` / `aeat_live_tests_enabled` token outside the core config/access-gate authority files and test infrastructure. The live-test opt-in environment and settings field names now live as central config constants, and auth operator settings scoping imports the neutral field-name constant instead of hardcoding the setting key. `W11.P25.S94` and `W11.P25.S96` remain open.

2026-06-04 marker-taxonomy closeout: `W11.P25.S96` is satisfied by the shared marker hook plus marker-integrity coverage. The hook enforces exactly one access marker, drops `live_write` at collection with no bypass, and skips `live_read` unless the pytest live-test opt-in is truthy. The marker-integrity suite now covers marker registry uniqueness, module-level marker placement, function-level marker refusal, live-test env runtime access scoping, and the production live-test opt-in token guard. The expanded focused run reported 2120 passing tests across marker integrity, gate behavior, auth login behavior, and config/env-example alignment.
