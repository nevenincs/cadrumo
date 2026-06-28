---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'AUTH-LIVE-HARDENING'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` Auth Live Hardening

Hardened the live AEAT Cl@ve path exposed while trying to run the IVA wallet live-read tests against the active operator profile.

- Modified: `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
- Modified: `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py`
- Modified: `src/aeat/application/auth/_diagnostics.py`
- Modified: `src/aeat/application/auth/_operator.py`
- Modified: `src/aeat/application/auth/__init__.py`
- Modified: `src/aeat/application/auth/test_diagnostics.py`
- Modified: `src/aeat/application/live/test_iva_wallet_live.py`
- Modified: `src/aeat/application/conftest.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_workflow_surface.py`
- Modified: `src/aeat/entrypoints/cli/_live.py`
- Modified: `src/aeat/core/external_constants.py`
- Modified: `src/aeat/core/external_constants.toml`
- Modified: `src/aeat/core/test_external_constants.py`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/hu.yml`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`

## Description

The first live test run failed before reaching AEAT because direct tests were not running under the CLI root bucket-session opener. The adapter and application live tests now explicitly bind the active master-key provider, and application live tests no longer inherit the unit-test storage sandbox.

The next live run reached AEAT's non-QR Cl@ve page. The encrypted diagnostic showed the page rendered a verification code, but the driver did not extract it from the current HTML shape. The driver now uses the configured selector only as a fast probe and falls back to extracting `Código de verificación` from rendered page text.

The timeout path also left a Cl@ve request pending server-side. New timeout attempts now capture the encrypted diagnostic and then attempt to invoke AEAT's cancellation control before closing the browser context. Cancellation is bounded so a stuck page cannot mask the original timeout, and it is only logged as confirmed when AEAT's cancellation response is observed. The cancellation response marker is declared through the external constants registry, not embedded as a driver-local URL.

The live tests no longer repeat the parser-local row summation as an assertion. The application live test still writes durable encrypted evidence to the active operator bucket by design; that is the behavior under verification and remains opt-in/live-gated rather than part of default unit selection.

The config CLI now has an explicit live login surface. `aeat config auth test` remains a readiness probe, while `aeat config auth login` delegates to the central `ensure_authenticated_aeat_session` backend, supports persisted-session reuse, `--fresh`, and `--reset-lock`, and records a verified workflow auth state only after the backend has verified the AEAT session. The login result exposes only redacted operational fields: provider, authenticated flag, reuse/fresh flags, removed-session count, lock acquisition, reset-lock state, and verification status.

Encrypted auth diagnostics now carry and display redacted attempt context for new captures: auth branch, identity kind, headed/headless mode, configured contrast-factor presence, and timeout. The diagnostic CLI also has `aeat config auth diagnostics report DIAGNOSTIC_ID --phone-state ...` so the operator can attach the actual Cl@ve app state to a diagnostic after a timeout. The allowed values are `app_prompted_and_accepted`, `app_prompted_not_accepted`, `app_did_not_prompt`, and `operator_did_not_check`; invalid values are refused before persistence.

## Tests

`uv run ruff check src/aeat/entrypoints/cli/_live.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/application/conftest.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/test_iva_wallet_live.py src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py` passed.

`uv run pytest src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestClaveWaitState::test_extracts_verification_code_from_rendered_non_qr_html -q --disable-warnings` passed.

`uv run pytest src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/test_iva_wallet_live.py -q --disable-warnings` completed with 20 passed and 2 live-gated deselected.

`uv run pytest -m live_read src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py -q --disable-warnings -s` currently reaches the AEAT auth boundary but fails fast because AEAT reports a prior Cl@ve request pending server-side.

After the cancellation confirmation fix, a background live run reached AEAT's non-QR Cl@ve page, emitted a verification code, waited for the configured 120 seconds, timed out without receiving AEAT's post-auth redirect, captured encrypted diagnostic `20260520T142929Z`, and confirmed AEAT cancellation of the pending request. No wallet page read occurred because authentication did not complete.

Operator testimony then clarified the intended behavior: the production Cl@ve Móvil flow should surface an app notification/approval for the configured identity, and no such notification was observed during the non-QR attempts. A separate QR/headed run was explicitly forced with process-local overrides to inspect the alternate driver branch; it opened a visible QR page and is therefore an implemented mode, but it is not the persistent configured default. Persistent settings after the run remained `aeat_clave_prefer_non_qr=True`, `aeat_browser_headless=True`, provider `clave_movil`, and timeout `120000`.

The live wallet blocker is therefore narrowed to the intended non-QR Cl@ve path: AEAT renders the wait page and verification code, but the operator does not see a corresponding app notification and the browser never receives AEAT's post-auth redirect.

`uv run aeat config auth login --provider clave_movil` exercised the explicit live login surface, reached the non-QR Cl@ve wait page, timed out after 120 seconds without AEAT post-auth redirect, and captured encrypted diagnostic `20260520T152302Z`. No wallet page read occurred because authentication did not complete. No phone-state report was recorded for that diagnostic in this pass because the operator had not supplied the observation for this specific attempt.

A subsequent `uv run aeat config auth login --provider clave_movil` retry reached the same non-QR Cl@ve wait page with verification code present, timed out after 120 seconds without AEAT post-auth redirect, and captured encrypted diagnostic `20260520T160230Z`. No wallet page read occurred because authentication did not complete, and no phone-state report was recorded because the operator had not supplied the observation for this specific attempt.

A later non-QR Cl@ve retry completed after operator approval. `uv run aeat config auth status --provider clave_movil` then reported `authenticated=True` and `available=True`, confirming the backend login persistence path.

`uv run aeat app live iva-wallet capture-history --from-year 2024 --to-year 2024` completed with four captured observations and four reloaded secure history rows. `uv run aeat app live iva-wallet capture-history --from-year 2023 --to-year 2023` completed with four additional observations and eight total reloaded secure history rows.

Focused filed captures isolated an older artefact parser gap: a 2022 Modelo 303 filed capture persisted evidence but extracted zero casillas, while focused 2023 and 2024 captures extracted casillas and promoted into calculation observations. No private values were copied into the vault note.

`uv run aeat app live iva-wallet pull --year 2026 --period 2T` first exposed a generic Cl@ve target-verification failure for the wallet URL. The application wallet capture was changed to verify the general Sede session first and let the wallet driver navigate to the wallet URL. After that change, the wallet driver reached AEAT's concrete result: redirect to `erro4033.html` for the direct wallet URL. The public AEAT Modelo 303 "Gestiones IVA" page links to the same wallet URL, and opening that official link without a certificate returns AEAT 403 text indicating that no electronic certificate was detected or correctly selected. Follow-up official-source research corrected the interpretation: AEAT's Pre303 FAQ says access to Pre303 and its utilities requires `Certificado o DNI electrónico o clave PIN`. Current evidence therefore points to an incomplete direct URL/selector route in the driver, not proof that Cl@ve lacks access to the wallet state.

The wallet/Pre303 constants pass moved the remaining current-surface literals into `external_constants.toml` and typed schema fields: AEAT host suffix, the generic Sede 4033 auth-gate path, Pre303 presentation-service path, Pre303 official documentation paths, Pre303 access-method wording, G313 census launcher path, and wallet table header markers. The wallet driver and NIF-IVA auth-gate detector now consume the same centralized host/path constants, wallet-facing tests use the exported canonical `IVA_COMPENSATION_WALLET_URL`, the Pre303 and Mis Datos Censales portal entries consume schema-backed paths, and Sede-origin Settings defaults derive from the external constants registry.

The wallet live path now uses the centralized Pre303 presentation-service URL as its authentication target. `capture_iva_compensation_wallet` passes that target to the auth session acquisition, and `fetch_iva_compensation_wallet` navigates to the Pre303 presentation service before navigating to the independent wallet URL for read-only parsing. This follows AEAT's documented route from Pre303/casilla 110 while still recording the canonical wallet URL as the source of the parsed wallet observation.

The live wallet path is now end-to-end functional for the active profile. Explicit Cl@ve target verification dispatches through AEAT's selector instead of directly probing the app URL. The wallet reader also opens Pre303 and the wallet through the selector, continues AEAT's own-name representation gate only when AEAT has already selected own-name mode, and submits the wallet execute control only when the form action path matches the configured wallet route. The parser recognizes the exact authenticated empty-wallet shell as a zero-row wallet observation; unrecognized pages still fail as `external_shape_changed`.

An intermediate diagnostic exposed arbitrary AEAT button/body text, which can include operator display text. That diagnostic surface was tightened in the same pass: wallet shape errors now report structural fields only, not arbitrary page text or button labels.

The code-review pass found two high-risk issues in that first live-complete version. The wallet execute control was a live POST that had not been classified by the remote-state guard, and the parser could infer a zero wallet from the pre-execute wallet shell. Both were corrected before closing this step: the remote-state guard now supports explicit authenticated read POST paths, the wallet policy allows only the configured `CarteraCuotas` path, and empty-wallet parsing is enabled only after the live reader confirms the execute gate was submitted. The standalone parser refuses the same shell by default.

The same review also found broad Cl@ve landing acceptance and text-bearing diagnostics. Cl@ve verification now accepts only exact target URLs or same AEAT application paths. Wallet parse diagnostics no longer include title text, headings, table headers, body text, or button labels. Cl@ve timeout output now reports URL host/path/query-key shape rather than full query values.

`uv run aeat config auth diagnostics report 20260520T152302Z --phone-state guessed` refused the invalid phone-state value and listed the allowed values.

`uv run aeat config auth diagnostics report --help` rendered the locale-backed command help.

`uv run ruff check src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/__init__.py src/aeat/application/auth/test_diagnostics.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_workflow_surface.py` passed.

`uv run ruff check src/aeat/application/live/__init__.py` passed after the wallet capture target-verification change.

`uv run pytest src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/core/test_external_constants.py src/aeat/application/auth/test_diagnostics.py src/aeat/entrypoints/cli/test_workflow_surface.py::test_config_auth_accepts_supported_provider_and_rejects_others -q --disable-warnings` completed with 46 passed.

`uv run ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py src/aeat/adapters/outbound/aeat/sede/__init__.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py` passed.

`uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py -q --disable-warnings` completed with 41 passed.

`uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/domain/portals -q --disable-warnings` completed with 99 passed.

`uv run pytest src/aeat/core/test_external_constants.py src/aeat/domain/portals src/aeat/application/live/test_census_snapshot.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py -q --disable-warnings` completed with 147 passed.

`uv run pytest src/aeat/core/test_external_constants.py src/aeat/domain/portals src/aeat/application/live/test_census_snapshot.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py -q --disable-warnings` completed with 162 passed after the final production-comment scrub.

`uv run python -m aeat.locales audit` reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok after removing the unused `application.setup.errors.workspace_bucket_torn` YAML key.

`uv run ruff check src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/__init__.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/__init__.py` passed after retargeting wallet authentication to Pre303.

`uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_iva_wallet_live.py -q --disable-warnings` completed with 5 passed and 1 live-gated deselected.

`uv run aeat app live iva-wallet pull --year 2026 --period 2T` completed successfully after the selector/representation/execute fixes. The command persisted encrypted wallet evidence, reloaded/reconciled it, selected AEAT wallet authority, reported zero wallet rows, and returned an unblocked decision. No private wallet values were copied into this step record.

`uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/application/auth/_sessions.py src/aeat/application/wizard/_commands.py src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py` passed.

`uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/application/auth/test_ensure_session.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_iva_wallet_live.py -q --disable-warnings` completed with 60 passed and 1 live-gated deselected.

The mandatory code-review pass reported two HIGH issues and three MEDIUM issues. The HIGH issues were resolved in code before finalization; the MEDIUM auth-landing and diagnostic issues were also resolved. The remaining LOW test-style concern is tracked as existing protocol-test debt rather than a blocker for this live wallet fix.

`uv run ruff check src/aeat/domain/calculations/registry/_remote_state_guard.py src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py` passed after the review fixes.

`uv run pytest src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/application/live/test_iva_wallet_capture_backend.py -q --disable-warnings` completed with 73 passed after the review fixes.

A strict live retry after the review fixes did not reach the wallet reader because Cl@ve authentication timed out after 120 seconds. That retry produced diagnostic `20260520T221522Z` with sanitized URL context. The stricter execute/empty-wallet rules are therefore locally verified and require a fresh operator-approved live retry for final live reconfirmation.

On 2026-05-21, another strict live retry was started while the operator was ready for auth. The CLI rendered verification code `X2A`, but AEAT did not complete the browser-side Cl@ve redirect within 120 seconds. The command produced diagnostic `20260521T061613Z`; its CLI-visible URL context was sanitized to host/path/query-key names. The wallet reader was not reached in this run. Operator phone-state testimony is still required before recording the diagnostic report.

The operator then reported that no approval prompt was received for that attempt. `uv run aeat config auth diagnostics report 20260521T061613Z --phone-state app_did_not_prompt` recorded the phone-state testimony. A local configuration check confirmed the configured Cl@ve identity is present, is a NIE, has the expected length, and matches the operator-supplied prefix; the full identifier was not copied into this note.

Follow-up verification found that `aeat config auth diagnostics show` still emitted the stored Cl@ve URL with query values. The application diagnostic projection now redacts stored diagnostic URLs to host/path plus query-key names, and regression coverage confirms sensitive query values are not emitted. `uv run aeat config auth diagnostics show 20260521T061613Z` now renders the sanitized URL shape and the recorded `app_did_not_prompt` phone state.

On 2026-05-21, profile/auth alignment was rechecked after the operator clarified that `env/.env` is not the live profile authority. The active profile was `roger-design`, and `aeat config auth configure --provider clave_movil` reported `identity_alignment=mismatch`. A redacted profile scan found exactly one live profile matching the configured Cl@ve identity: `live-operator-active`. The profile was switched, Cl@ve auth was configured there, and the serial status check reported `identity_alignment=matches`, `configured=True`, and `available=True`.

This exposed a critical backend gap: live Cl@ve auth could be attempted even when the active profile tax identity and the configured Cl@ve identity diverged. The central auth session path now enforces that alignment before persisted-session reuse or fresh authentication, and rejects reused sessions whose identity differs from the active profile expectation. The guard emits no tax identifiers. The Cl@ve timeout suggestion also now gives the concrete `aeat config auth diagnostics report DIAGNOSTIC_ID --phone-state ...` command shape.

A fresh wallet pull was then attempted for 2026 `2T`. The CLI rendered verification code `DHM`, waited for the configured 120 seconds, and timed out without AEAT completing the post-auth browser redirect. It produced diagnostic `20260521T064750Z`. No wallet data was read or persisted in this retry, and the operator's phone-state testimony is still required before recording that diagnostic report.

`uv run ruff check src/aeat/application/auth/_sessions.py src/aeat/application/auth/__init__.py src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_ensure_session.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/core/errors/registry/_application.py` passed.

`uv run pytest src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_ensure_session.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -q --disable-warnings` completed with 44 passed.

The operator then reported that no phone auth request arrived and identified profile/identity association as the likely failure mode. Diagnostic `20260521T064750Z` was recorded with `phone_state=app_did_not_prompt`.

New Cl@ve diagnostics now persist a redacted auth-configuration snapshot with each future diagnostic: active profile id/label, profile registration and profile-record presence, profile tax-id presence, identity alignment, Cl@ve identity kind/configured flag, DNI date/NIE support-factor presence, non-QR/headless/timeout settings, certificate path/password/file/backend state, and short SHA-256 fingerprints for profile tax id, Cl@ve identity, contrast factors, and certificate path. Raw NIE, support number, dates, and certificate paths are not emitted. `aeat config auth diagnostics list` now includes profile/alignment, and `show` renders the full redacted snapshot.

`uv run aeat config auth diagnostics show 20260521T064750Z` now shows the recorded `app_did_not_prompt` phone state. The new profile snapshot fields are blank on that older diagnostic because it predates the snapshot fix.

A direct diagnostic-context probe against the current active profile reported profile `live-operator-active`, `identity_alignment=matches`, profile record/tax-id present, NIE support configured, and no certificate configured; only booleans and fingerprints were printed.

A fresh live wallet retry emitted verification code `35X`, timed out after 120 seconds, and produced diagnostic `20260521T071445Z`. The diagnostic now shows active profile `live-operator-active`, `identity_alignment=matches`, matching profile/Cl@ve identity fingerprints, NIE support configured, and no certificate configured. This rules out the earlier wrong-active-profile explanation for the latest timeout. Phone-state testimony for this newest attempt remains pending.

`uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py src/aeat/entrypoints/cli/_config/__init__.py` passed.

`uv run pytest src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_ensure_session.py src/aeat/application/auth/test_diagnostics.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -q --disable-warnings` completed with 45 passed.

On 2026-05-21, a further live wallet retry emitted Cl@ve verification code `KLS`. The operator later confirmed the phone-side issue was resolved and the request was approved. The browser then reached AEAT's representation gate and the command failed closed before wallet capture. This is now classified as an authenticated read-surface routing/safety issue, not as a missing Cl@ve notification issue.

The safety policy was then narrowed after the operator clarified that the representation gate is an acting-capacity selector, not a filing surface. Own-name continuation for the already-authenticated profile user is now allowed because it identifies the authenticated user as acting for themselves. Representative/third-party mode remains blocked: the driver does not fill represented-party NIF/name fields and fails closed if the own-name selector is unavailable or the gate shape is unknown. The centrally declared browser action is `representation-gate-own-name-continue`.

The focused constants pass for the auth/wallet surface added missing TOML-backed schema entries for the AEAT `www12` origin and Cl@ve Móvil representation, QR, non-QR, DNI/NIE contrast, and cancellation paths. The Cl@ve Móvil and IVA wallet tests touched in this pass no longer hardcode AEAT origins, Sede paths, wallet paths, or selectors; they derive them from `Settings.external_constants()` or exported canonical URLs. A broader repo cleanup is still required for older tests that predate this mandate and still embed AEAT URLs.

`uv run ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py` passed.

`uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py -q --disable-warnings` completed with 63 passed.

`git diff --check -- src/aeat/core/external_constants.py src/aeat/core/external_constants.toml src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py` passed.
