---
tags:
  - '#plan'
  - '#live-iva-compensation-wallet'
date: '2026-05-19'
modified: '2026-05-19'
tier: L3
related:
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
  - '[[2026-05-26-modelo-130-relation-regression-adr]]'
  - '[[2026-05-26-modelo-130-relation-regression-plan]]'
  - '[[2026-04-17-aeat-access-gate-adr]]'
  - '[[2026-04-17-session-persistence-adr]]'
  - '[[2026-04-16-live-cert-auth-adr]]'
  - '[[2026-05-26-live-iva-auth-read-acquisition-adr]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
  - '[[2026-05-26-aeat-sede-constants-centralization-adr]]'
---


# `live-iva-compensation-wallet` `implementation` plan

## Papertrail Control

This plan is the current binding execution plan for the live IVA compensation
wallet, filed-history, secure-profile persistence, and multiyear IVA
reconciliation work. The governing ADR chain is declared in the `related`
frontmatter. No substantial implementation slice may proceed unless it maps to
one of the rows below and to an accepted ADR in that chain.

| Work area | Plan rows | Governing ADR basis | Execution gate |
| --- | --- | --- | --- |
| Read-only wallet/filed-history authority and source separation | Waves 01, 03, 06, 07, and 08 | `2026-05-26-live-iva-auth-read-acquisition-adr`; `2026-05-26-live-iva-remote-evidence-reconciliation-adr`; profile/bucket/repository/binding reconciliation ADR | AEAT evidence, filed-history evidence, local recurrence, and taxpayer override remain separate; persisted non-blocking decisions are required before remote-state values affect outputs. |
| Live auth diagnostics and identity confirmation | Wave 05 | `2026-05-26-live-iva-auth-read-acquisition-adr`; AEAT access gate ADR; session persistence ADR; live certificate/auth ADR | Diagnostics must be redacted, must identify configured profile shape, and must never infer operator approval without observable evidence. |
| No live submission or synthetic AEAT-hosted input | Wave 02, Wave 06 representation-gate rows, and Wave 09 validation rows | no-synthetic Sede ADR; `2026-05-26-live-iva-auth-read-acquisition-adr` | Drivers may authenticate and read only. Filing, payment, represented-taxpayer choice, confirmation, and synthetic inputs to AEAT-hosted surfaces are prohibited. |
| Secure profile persistence and reload | Wave 07 and Wave 09 storage-centralization rows | `2026-05-26-live-iva-remote-evidence-reconciliation-adr`; secure-storage production hardening ADR; profile/bucket/repository/binding reconciliation ADR | Remote IVA evidence must persist through active-profile `StorageRuntime` repositories and reload without live login. |
| Multiyear IVA compensation grounding | Waves 03 and 08 | `2026-05-26-live-iva-remote-evidence-reconciliation-adr`; Modelo 303/390 IVA ADRs; IVA compensation chain ADR | Local recurrence is diagnostic/fallback evidence. Available AEAT evidence is binding external state, and unresolved divergence blocks filing-grade output. |
| Modelo 130 relation-regression coupling | Wave 08 Modelo 130 relation row | Modelo 130 relation-regression ADR and plan | Modelo 130 remains separate IRPF work. Shared infrastructure changes must not treat Modelo 130 carry-forward as IVA compensation authority. |
| Constants/settings/schema centralization | Wave 09 | `2026-05-26-aeat-sede-constants-centralization-adr`; secure-storage production hardening ADR; no-synthetic Sede ADR | AEAT/Sede executable constants, Cl@ve waits, live action labels, and test database password constants must live in `Settings`, `external_constants.toml`, registry TOML/YAML, or typed schema models. |

Rows that are not covered by an accepted ADR are blocked. The next valid action
for an uncovered row is research and an ADR amendment or new ADR, not code.

## Wave `W01` - live wallet read authority

This Wave builds the live AEAT read path and makes it the primary authority for
the Modelo 303 prior compensation binding. It must precede treating the IVA
calculation chain as production-complete.

### Phase `W01.P01` - declare read-only wallet surface and state records

This Phase records AEAT's wallet endpoint, strict read-only evidence schema, and
the internal reconciliation decision record that calculation code will consume.

- [x] `W01.P01.S01` - add the wallet path and tests to the external constants registry; `src/aeat/core/external_constants.toml`.
- [x] `W01.P01.S02` - add strict wallet observation and row schemas; `src/aeat/adapters/outbound/aeat/sede/_schema.py`.
- [x] `W01.P01.S03` - add wallet reconciliation decision and divergence status records; `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `W01.P01.S04` - add wallet remote-operation guard policy and export surface; `src/aeat/adapters/outbound/aeat/sede/__init__.py`.

### Phase `W01.P02` - implement authenticated wallet capture

This Phase adds the Cl@ve/certificate-backed read driver and parser.

- [x] `W01.P02.S05` - implement `fetch_iva_compensation_wallet` as a read-only Sede adapter; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [x] `W01.P02.S06` - add parser coverage from captured wallet HTML fixtures; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [x] `W01.P02.S07` - add opt-in live smoke coverage gated by `AEAT_LIVE_TESTS_ENABLED`; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py`.

### Phase `W01.P03` - persist wallet evidence

This Phase stores wallet observations so calculation prefill can use the latest
authenticated AEAT evidence without requiring a live login on every calculation.

- [x] `W01.P03.S08` - add encrypted persistence support for wallet observations; `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`.
- [x] `W01.P03.S09` - add repository roundtrip tests for wallet observations; `src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py`.
- [x] `W01.P03.S10` - add encrypted persistence support for wallet reconciliation decisions; `src/aeat/application/calculations/_observations_repository.py`.
- [x] `W01.P03.S11` - add backend workflow entry point for operator-approved wallet pull; `src/aeat/application/live/__init__.py`.

### Phase `W01.P04` - reconcile and prefill Modelo 303

This Phase connects wallet observations to the Modelo 303 prior compensation
binding and blocks silent divergence.

- [x] `W01.P04.S12` - implement local recurrence extraction for comparison without selecting the effective value; `src/aeat/application/calculations/_binding_prefill.py`.
- [x] `W01.P04.S13` - implement wallet, override, local recurrence authority selection and blocking divergence statuses; `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `W01.P04.S14` - consume only non-blocking reconciliation decisions for Modelo 303 prior compensation prefill; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P04.S15` - prevent automatic output when the wallet reconciliation decision is blocked; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P04.S16` - add divergence scenario tests for match, AEAT-higher, AEAT-lower, stale wallet, missing wallet, and explicit taxpayer override; `src/aeat/application/calculations/test_iva_wallet_reconciliation.py`.
- [x] `W01.P04.S17` - run wallet, Modelo 303, Modelo 390, and relation-regression focused suites together; `tests`.

## Wave `W02` - live AEAT no-submit safety hardening

This Wave closes the safety gap discovered during live wallet route hardening:
an automated wallet read must never submit AEAT filing, payment, confirmation,
represented-taxpayer, or operator-choice form data. The only currently accepted
exception is the centrally guarded wallet read-query POST for the authenticated
`CarteraCuotas` surface, after the driver proves the form action matches the
configured wallet path. A live wallet capture may authenticate and may navigate
through explicit read URLs, but it must fail closed before any unclassified
wallet execute, representation, presentation, filing, confirmation, or mutation
control is clicked.

### Phase `W02.P05` - fail closed before wallet or representation form actions

This Phase hardens the live wallet reader around AEAT form boundaries. The
driver may authenticate and navigate to read surfaces, but it must refuse
unclassified wallet execute shells, unrecognized empty-wallet pages, and
representation choices that would post taxpayer or represented-party intent to
AEAT. Any wallet read-query exception must be explicit in the remote-state guard
and verified by parser fail-closed tests.

- [x] `W02.P05.S18` - block the wallet execute gate by static HTML inspection without running page JavaScript; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [x] `W02.P05.S19` - remove any wallet POST allowance from the read guard and prove wallet POST is rejected; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [x] `W02.P05.S20` - reject no-table wallet shells instead of interpreting them as zero-balance observations; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [x] `W02.P05.S21` - fail closed on AEAT representation-gate submission in wallet capture and Cl@ve verification; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py, src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.

### Phase `W02.P06` - audit every live AEAT browser action

This Phase turns live browser actions into an explicit allow-list contract.
Every click, fill, evaluate, navigation, and POST-capable interaction is
classified before use so new AEAT automation cannot enter the codebase without
an audited read-only or authentication-only safety label.

- [x] `W02.P06.S22` - enumerate every live AEAT click, fill, evaluate, navigation, and POST-capable browser action across Sede/auth adapters; `src/aeat/adapters/outbound/aeat`.
- [x] `W02.P06.S23` - classify each action as authentication-only, read-only navigation, diagnostic cleanup, or forbidden live submission; `src/aeat/adapters/outbound/aeat`.
- [x] `W02.P06.S24` - move accepted action markers into external constants and guard policies; `src/aeat/core/external_constants.toml, src/aeat/domain/calculations/registry/_remote_state_guard.py`.
- [x] `W02.P06.S25` - add tests that fail when new live AEAT form-submission paths are introduced without explicit safety classification; `src/aeat/adapters/outbound/aeat`.

## Wave `W03` - complete IVA calculation engine verification

This Wave expands the wallet work into the broader IVA calculation engine:
ledger evidence must flow into periodic IVA forms, annual summaries, cross-year
carry-forward state, and AEAT remote-state reconciliation without duplicated
business logic or silent authority inversions.

### Phase `W03.P07` - ledger-to-periodic IVA calculation chain

This Phase proves ledger evidence reaches periodic Modelo 303 calculations
through production aggregation and registry bindings. The tests must exercise
ordinary IVA, special regimes, reverse-charge and adjustment cases without
duplicating Modelo 303 arithmetic inside assertions.

- [x] `W03.P07.S26` - verify ledger aggregation inputs for ordinary IVA, recargo equivalencia, exenciones, OSS/IOSS, intra-community operations, and adjustments; `src/aeat/application/aggregation, src/aeat/domain/iva`.
- [x] `W03.P07.S27` - verify Modelo 303 periodic casilla bindings consume registry formulas and ledger observations rather than mirrored test arithmetic; `src/aeat/application/modelo, src/aeat/domain/calculations/registry`.
- [x] `W03.P07.S28` - add traceable calculation tests from ledger rows to Modelo 303 outputs for positive, negative, zero, and compensation-applied periods; `src/aeat/application/aggregation, src/aeat/application/modelo`.

### Phase `W03.P08` - yearly IVA summary forms

This Phase verifies the annual IVA summary path against the quarterly Modelo
303 evidence it summarizes. Modelo 390 coverage must reconcile annual fields
to produced quarterly observations and block unsupported regimes instead of
silently inferring values outside the registry.

- [x] `W03.P08.S29` - verify Modelo 390 annual fields reconcile against four Modelo 303 periods, including casillas `97` and `662`; `src/aeat/domain/calculations/registry, src/aeat/application/modelo`.
- [x] `W03.P08.S30` - verify annual summary behavior for regimes represented in the ledger catalogue and identify unsupported regimes as blocking gaps rather than inferred formulas; `src/aeat/domain/iva, src/aeat/domain/calculations/registry`.
- [x] `W03.P08.S31` - add cross-form tests that compare annual totals to periodic observations without reimplementing form business logic in tests; `src/aeat/application/modelo, src/aeat/domain/calculations/registry`.

### Phase `W03.P09` - cross-year and multiyear carry-forward tracking

This Phase models IVA compensation as dated carry-forward lots rather than a
single same-year aggregate. Source period, age, applied amount, remaining
balance, expiry state, and AEAT/local divergence must remain visible across
fiscal years.

- [x] `W03.P09.S32` - model carry-forward age, source period, applied amount, remaining amount, and expiry review state across fiscal years; `src/aeat/application/calculations, src/aeat/domain/iva`.
- [x] `W03.P09.S33` - enforce LIVA art. 99 four-year compensation-window policy from dated evidence rather than same-year recurrence only; `src/aeat/application/calculations, src/aeat/domain/calculations/registry`.
- [x] `W03.P09.S34` - add multiyear tests for generation year, application year, expiry boundary, AEAT wallet divergence, and local filed-history fallback; `src/aeat/application/calculations, src/aeat/application/modelo`.

### Phase `W03.P10` - AEAT remote-state reconciliation ladder

This Phase establishes the authority ladder for remote-state values. AEAT
wallet evidence, local recurrence, filed-history observations, and taxpayer
overrides stay separate, and only persisted non-blocking decisions may affect
calculation, verification, or export.

- [x] `W03.P10.S35` - require persisted non-blocking reconciliation decisions before remote-state values affect form outputs; `src/aeat/application/calculations, src/aeat/application/modelo`.
- [x] `W03.P10.S36` - keep AEAT wallet evidence, local recurrence, filed-history observations, and explicit taxpayer overrides as separate authority sources; `src/aeat/application/calculations`.
- [x] `W03.P10.S37` - surface blocked reconciliation states through CLI/workflow before any calculation/export path can proceed; `src/aeat/entrypoints/cli, src/aeat/application/filing`.

## Wave `W04` - CLI operator-persona testimonial verification

This Wave turns CLI usage into first-class evidence. Subagents/personas operate
the official CLI, record what they attempted, what worked, where they hesitated,
and which outputs were insufficient for safe tax work. No persona may enter real
taxpayer secrets or perform live AEAT submission.

### Phase `W04.P11` - persona briefs

This Phase defines the operator personas used to test the wallet and IVA
pipeline through the official CLI. Each persona receives a bounded task brief
that forbids live AEAT submission and asks for practical friction, safety, and
calculation-surface feedback.

- [x] `W04.P11.S38` - brief a first-run autónomo persona to create/switch a profile, import or enter ledger evidence, calculate a Modelo 303 period, and report friction; `.vault/audit`.
- [x] `W04.P11.S39` - brief a returning accountant persona to inspect filed-history/ledger state, calculate four quarters, prepare Modelo 390, and report reconciliation gaps; `.vault/audit`.
- [x] `W04.P11.S40` - brief a live-wallet reviewer persona to run the official live wallet CLI path only up to the fail-closed safety boundary, verify no AEAT filing/payment/represented-taxpayer choice is submitted beyond the guarded wallet read query, and report the operator experience; `.vault/audit`.
- [x] `W04.P11.S41` - brief a multiyear compensation reviewer persona to exercise cross-year carry-forward scenarios and report whether the CLI exposes source-period age and authority decisions clearly; `.vault/audit`.

### Phase `W04.P12` - testimonial capture and audit integration

This Phase converts persona CLI testimony into implementation evidence.
Commands, redacted outputs, hesitation points, and safety observations are
captured in the audit log, then repeated friction is promoted into concrete
follow-up tasks and reviewed after each fix.

- [x] `W04.P12.S42` - capture persona commands, redacted outputs, friction points, and safety observations in audit notes; `.vault/audit`.
- [x] `W04.P12.S43` - convert repeated persona friction into concrete implementation tasks with severity and file/module ownership; `.vault/plan, .vault/audit`.
- [x] `W04.P12.S44` - run code-review after each persona-driven implementation step and append findings to the wallet/IVA audit log; `.vault/audit`.

Discovered implementation tasks from W04.P02 persona evidence:

- `W04.F01` - HIGH - FIXED - Modelo readiness must incorporate ledger preflight/readiness for ledger-owned Modelo 303 bindings so a period with unclassified or incomplete ledger evidence cannot report ready while calculation emits zero IVA values; owner modules: `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/ledger`, `src/aeat/application/aggregation`, `src/aeat/application/modelo`.
- `W04.F02` - MEDIUM - FIXED - ledger view/status should surface tax-relevant fields needed for IVA calculation diagnostics, including category, taxable base, IVA rate, IVA amount, and classification-readiness state; owner modules: `src/aeat/entrypoints/cli/_ledger.py`, `src/aeat/application/ledger`.
- `W04.F03` - HIGH - FIXED - live IVA wallet CLI help/output should explicitly name the representation-gate fail-closed policy and the fact that no AEAT form choices are posted; owner modules: `src/aeat/entrypoints/cli/_app_live.py`, `src/aeat/adapters/outbound/aeat/auth`, `src/aeat/adapters/outbound/aeat/sede`.
- `W04.F04` - HIGH - FIXED - CLI surfaces must expose IVA compensation carry-forward lots, source-period age, expiry review state, and persisted authority-source decisions; owner modules: `src/aeat/entrypoints/cli/_app_live.py`, `src/aeat/application/calculations`, `src/aeat/application/modelo`.
- `W04.F05` - MEDIUM - FIXED - verify/export wallet-block guards must accept an injected `IvaWalletDecisionRepository` matching the caller's secure SQL repositories; owner modules: `src/aeat/application/modelo/_actions.py`, `src/aeat/application/modelo/_export.py`, `src/aeat/application/modelo/test_export.py`.
- `W04.F06` - MEDIUM - FIXED - older live Sede/auth executable code must not embed AEAT hosts, route fragments, wallet paths, or selector access literals outside the external constants registry; owner modules: `src/aeat/core/external_constants.*`, `src/aeat/adapters/outbound/aeat/verify`, `src/aeat/adapters/outbound/aeat/sede`.
- `W04.F07` - HIGH - FIXED - older filed Modelo 303 submitted-file extraction must parse 2022 page-03 result casillas from the official 2022 record-design positions instead of the newer 2023+ layout; owner modules: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`, `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`.
- `W04.F08` - HIGH - FIXED - wallet empty-result interpretation must fail closed when the post-query page still exposes the executable wallet submit control and no wallet table; owner modules: `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`, `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- `W04.F09` - MEDIUM - FIXED - wallet safety plan wording must distinguish prohibited AEAT filing/payment/represented-taxpayer submissions from the centrally guarded wallet read-query POST; owner modules: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`.
- `W04.F10` - HIGH - FIXED - CLI and Modelo export tests must use active profile-bucket storage routes, file/ephemeral custody sessions, and injected wallet-decision repositories rather than explicit root database URLs; owner modules: `src/aeat/entrypoints/cli/test_workflow_surface.py`, `src/aeat/application/modelo/_export.py`, `src/aeat/application/modelo/test_export.py`, `src/aeat/application/user_profile/_orchestration.py`.
- `W04.F11` - HIGH - FIXED - split Modelo 303 registry layout must have one authoritative declaration path; owner modules: `src/aeat/_data/registry/aeat/modelos/303.toml`, `src/aeat/_data/registry/aeat/modelos/303/`.
- `W04.F12` - MEDIUM - PARTIAL - drain remaining EphemeralMasterKeyProvider default-repository tests now tracked by the storage hygiene guard. Session 2026-05-26 committed the first secure-SQL guard and helper slice in `177f0669a`; remaining owners must still be audited and repaired without fakes, monkeypatching, private taxpayer data, or root-database cross-contamination. Owner modules: `src/aeat/adapters/outbound/aeat/export/test_engine.py`, `src/aeat/adapters/persistence/profile/test_assets_roundtrip.py`, `src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py`, `src/aeat/application/calculations/test_binding_prefill.py`, `src/aeat/application/calculations/test_observations_repository_roundtrip.py`, `src/aeat/application/calculations/test_relation_prefill_source_mesh.py`, `src/aeat/application/modelo/test_declaration_period_binding.py`, `src/aeat/application/modelo/test_profile_binding.py`, `src/aeat/application/workflow/test_state_persistence_roundtrip.py`, `src/aeat/domain/buckets/test_event_history_roundtrip.py`, `src/aeat/domain/invoices/test_repository.py`, `src/aeat/domain/invoices/test_secure_storage_roundtrip.py`, `src/aeat/domain/justificante/test_secure_storage_roundtrip.py`, `src/aeat/domain/submission/test_secure_storage_roundtrip.py`.

## Wave `W05` - live auth diagnostics and identity confirmation

This Wave treats authenticated read access as a production-critical surface, not
a speculative CLI convenience. The driver must identify which configured
profile is being authenticated, classify the Cl@ve route that AEAT selected,
surface QR versus push behavior, expose timeouts within the accepted operator
window, and never infer that the operator approved a request without explicit
observable evidence.

### Phase `W05.P13` - configured identity and auth-route diagnostics

Record enough redacted configuration and browser-state evidence for the operator
to confirm the active profile before waiting on Cl@ve. Diagnostics must redact
taxpayer identifiers and support number values, but they must make clear whether
the configured profile has DNI/NIE, support-number, certificate, Cl@ve
preference, and timeout settings available.

- [x] `W05.P13.S45` - Add redacted live-auth preflight diagnostics for active profile identity, configured DNI/NIE presence, support-number presence, certificate provider state, Cl@ve preference, and timeout. Partial 2026-05-26: existing Cl@ve diagnostic payload fields for identity/config/certificate state are now exposed through the application diagnostic read model, including `prefer_non_qr` and `timeout_ms`; `CLI preflight rendering remains open. Completed 2026-05-27: `build_live_auth_preflight_report` now exposes a redacted application-owned preflight report, and IVA live CLI pull/capture-history commands render provider, active-profile, identity-alignment, route-mode, timeout, support-number presence, certificate state, and persisted-session presence to stderr before invoking live auth. Review follow-up 2026-05-27: the same preflight now runs before filed-history list/capture/capture-sources, DEHu notifications capture, and expedientes capture live-read entrypoints; `src/aeat/application/auth src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W05.P13.S46` - Classify and log the selected Cl@ve route as push, QR, non-QR fallback, certificate, or unknown without swallowing browser errors. Partial 2026-05-26: application diagnostics now classify captured AEAT auth URLs against centralized `external_constants.toml` Cl@ve/Sede routes; `driver-side start logging already records selected `auth_mode`; richer outcome taxonomy remains open. Completed 2026-05-27: Cl@ve fresh-login attempt context now records `auth_route`, encrypted diagnostics surface that route, and the provider start log records mode, route, identity kind, identity alignment, profile-tax-id presence, and headless state without raw identifiers; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/application/auth`.
- [x] `W05.P13.S47` - Enforce the operator-facing auth wait window from centralized settings, with a production default not exceeding 120 seconds for Cl@ve approval waits; `src/aeat/core/config.py src/aeat/adapters/outbound/aeat/auth`.
- [x] `W05.P13.S48` - Add real-behavior diagnostic tests that use production auth diagnostics and redaction logic without private taxpayer fixtures, fakes, stubs, or monkeypatched browser behavior. Partial 2026-05-26: `src/aeat/application/auth/test_diagnostics.py` now drives the real secure-object diagnostic read model with sanitized payloads and centralized AEAT route constants; `live-driver regression coverage remains open. Completed 2026-05-27: the real `ClaveMovilAuthProvider` attempt-context path is exercised against active profile secure storage and sanitized Cl@ve settings, proving route/mode/profile/support diagnostics are present while raw DNI/NIE and support values are absent. Review follow-up 2026-05-27: active profile identifiers and labels are now emitted only as redacted references/presence booleans in Cl@ve diagnostics, and an accidental secure-storage plan/audit inclusion was removed by a dedicated repair commit; `src/aeat/application/auth src/aeat/adapters/outbound/aeat/auth`.

- 2026-05-28 testimonial correction: the operator states they have never completed AEAT authentication in this work. Prior "live evidence" wording is reclassified as unauthenticated live-navigation/auth-attempt evidence only: browser attempts reached Cl@ve selector/routes and emitted encrypted diagnostics, but there is no accepted operator-confirmed AEAT login, no accepted filed-history read, and no accepted wallet/cartera read.

### Phase `W05.P14` - live-auth regression taxonomy

Convert the current ambiguous live-auth failures into typed outcomes so no 403,
missing prompt, QR fallback, timeout, wrong identity, or DOM drift is treated as
a generic unavailable state.

- [x] `W05.P14.S49` - Introduce typed live-auth acquisition outcomes for no-prompt, operator-timeout, QR-required, certificate-required, wrong-identity, AEAT-403, DOM-drift, and authenticated. Partial 2026-05-26: `LiveIvaAcquisitionFailureMode` and `classify_live_iva_acquisition_failure` now map Cl@ve and Sede adapter exceptions into application-level outcomes; `acquisition result wrapping and authenticated-success records remain open. Partial 2026-05-27: persisted Cl@ve session loading now accepts provider-specific encrypted metadata by narrowing it to provider-neutral identity, provider kind, authentication time, and idle deadline before parsing; these structural diagnostics must not be treated as operator-confirmed AEAT authentication. Completed 2026-05-27: `IvaRemoteStateAcquisitionReport` now carries a redacted auth outcome, per-surface outcomes expose `outcome_mode`, auth failures propagate typed modes to both filed-history and wallet surfaces, success records use `authenticated`, and certificate-required auth gates remain distinct from generic AEAT 403. Review follow-up 2026-05-27: legacy acquisition manifests that predate auth/outcome fields now validate with explicit legacy auth defaults instead of breaking profile reload; `src/aeat/adapters/outbound/aeat/auth src/aeat/application/auth src/aeat/application/live`.
- [x] `W05.P14.S50` - Propagate live-auth outcomes through CLI and backend result models using locale keys for operator-facing text. Completed 2026-05-28: the read-only `capture-remote-state` CLI renders redacted auth status, typed auth outcome, localized auth outcome label, provider/session diagnostics, and per-surface filed-history/wallet outcome labels from backend `IvaRemoteStateAcquisitionReport` fields. Review follow-up 2026-05-28: enum coverage now proves every current `LiveIvaAcquisitionFailureMode` resolves to operator-facing text and non-unknown modes do not collapse to the unknown label; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/locales`.
- [x] `W05.P14.S51` - Persist redacted live-auth diagnostic events in the current profile's secure storage route when a profile runtime is available. Completed 2026-05-28: live IVA auth outcomes now carry a redacted `diagnostic_ref` derived from auth exception diagnostic context; `persisted acquisition manifests and reloaded remote-state summaries expose only the hashed reference while the raw Cl@ve diagnostic remains in the encrypted auth diagnostics namespace. Tests prove raw diagnostic object keys do not appear in the report, manifest, or reloaded evidence; `src/aeat/application/live src/aeat/adapters/persistence/storage`.
- [x] `W05.P14.S52` - Add regression tests proving 403 and missing-prompt outcomes are not collapsed into success, zero-balance, or generic unavailable results. Partial 2026-05-26: application-level taxonomy tests now cover no-prompt, operator-timeout, QR-required, wrong-identity, AEAT-403, and DOM-drift classification. Completed 2026-05-28: combined acquisition report tests now assert missing-prompt auth failures keep auth and both surfaces failed with `no_clave_prompt`, and wallet/cartera 403 gates remain failed `aeat_403` outcomes without synthesized wallet success or zero-balance capture counts; `src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_live_failure_taxonomy.py`.

- 2026-05-28 testimonial correction: profile-bound secure storage setup and encrypted diagnostic/session writes are local infrastructure evidence only. They are not evidence of completed AEAT authentication. Remaining live status is blocked pending a fresh operator-observed auth attempt that reaches the target read surface.

## Wave `W06` - read-only Sede acquisition backend

This Wave makes live AEAT acquisition a backend capability first. CLI commands
may invoke it, but the authoritative behavior belongs to application services
and outbound Sede adapters. All live interactions remain read-only and must stop
before filing, payment, representation, or form-confirmation submission.
Local and synthetic tests may close wiring, taxonomy, persistence, and
fail-closed behavior only. Live acquisition functionality remains open until an
operator-observed, opt-in, read-only AEAT run completes authentication and
reaches the intended filed-history and wallet/cartera read surfaces.

2026-06-02 active priority and challenge statement: live IVA read-surface work
now outranks additional backend expansion. The backend storage, reconciliation,
taxonomy, and CLI paths are necessary but remain provisional until the
production Playwright driver can reach the authenticated AEAT read surfaces and
record only redacted aggregate evidence. Current known live blockers are
filed-history timeout diagnostics and wallet/cartera DOM drift; both must be
explained by research-backed route evidence before any calculation path may be
called grounded by AEAT's binding state. Official AEAT help confirms that
Modelo 303 declarations with result to pay or compensate may be absent from
`Mis expedientes` and should be consulted through `Consultar declaraciones
presentadas` or the Modelo 303 procedure query. Official AEAT declaration-query
help also documents Cl@ve as an accepted access method and describes required
search fields and filed-file download. Therefore the next coding slices must
prioritize the declaration-query route, authenticated DOM/trace diagnostics,
and a legally read-only wallet/cartera route assessment. Backend changes may
continue only when they directly unblock, preserve, or verify those live
read-only surfaces. Grounding sources searched on 2026-06-02:
`https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-303/incidencia-consultar-303-expedientes-no-todas.html`
and
`https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/consultas-informaticas/otros-servicios-ayuda-tecnica/consulta-declaraciones-presentadas.html`.

### Phase `W06.P15` - filed-history pull and wallet pull services

Implement a single read-only acquisition service that can pull filed-history
evidence and, where AEAT allows it, wallet/cartera evidence for the authenticated
profile.

- [x] `W06.P15.S53` - Build a backend read-only acquisition orchestration that authenticates once, fetches filed Modelo history across requested years, attempts wallet/cartera read, and returns typed evidence plus typed failures. Follow-up 2026-06-03: the orchestration is live-proven for the observed profile with persisted Cl@ve session reuse, separate filed-history and wallet/cartera success reporting, persisted acquisition manifest, and redacted reload. Completed 2026-06-04: non-private regression coverage now exercises the remote-state report/reload boundary together with multiyear submitted-file parser promotion; `src/aeat/application/live`.
- [x] `W06.P15.S54` - Keep wallet/cartera direct-read outcomes distinct from filed-history success so either surface can succeed or fail independently without discarding the other evidence source. Completed 2026-06-04: existing acquisition-report coverage preserves filed-history success when wallet/cartera fails, preserves wallet/cartera failure when history is absent, keeps auth failure separate from surface failure, and persists redacted per-surface outcomes; `src/aeat/application/live src/aeat/adapters/outbound/aeat/sede`.
- [x] `W06.P15.S55` - Add multi-year filed-history parsing coverage using sanitized official or committed corpus evidence only, never the operator's private tax history as a fixture. Completed 2026-06-04: a non-private test builds sanitized Modelo 303 submitted-file records, parses them through the Sede submitted-file parser, persists them through the production IVA compensation history path, reloads profile-local remote state, and proves cross-year carry-forward lots without private taxpayer fixtures; `src/aeat/adapters/outbound/aeat/sede src/aeat/application/live`.
- [ ] `W06.P15.S56` - Add and keep open an opt-in live read-only test path that requires operator-observed authentication and records only redacted diagnostics and aggregate evidence shape, not private taxpayer values. Follow-up 2026-06-03: wallet/cartera yielded parseable live AEAT cartera evidence through the read-only protected query path. Follow-up 2026-06-05: fresh Clave auth succeeded, the full 2022-2026 read-only remote-state capture reused the persisted session, filed-history and wallet/cartera both succeeded, and profile-local reload reported 12 history rows, 8 carry-forward lots, and 2 authority decisions. This row remains open as a standing live-verification path and privacy guard.; `src/aeat/application/live src/aeat/adapters/outbound/aeat/sede src/aeat/core`.

### Phase `W06.P16` - representation gate and read-only action boundary

The authenticated user is acting for the authenticated profile unless an
explicit representative mode is implemented later. Read-only acquisition may
identify the authenticated taxpayer where AEAT requires that to reach a read
surface, but it must not submit representation, filing, payment, or confirmation
intent.

- [x] `W06.P16.S57` - Rework representation-gate handling so own-profile read-only identity confirmation is allowed only when the guard classifies it as authentication/read navigation, not filing or representative submission; `src/aeat/adapters/outbound/aeat/sede src/aeat/domain/calculations/registry/_remote_state_guard.py`.
- [x] `W06.P16.S58` - Add guard tests for own-profile read navigation versus represented-taxpayer, filing, payment, and confirmation submissions; `src/aeat/adapters/outbound/aeat/sede src/aeat/domain/calculations/registry`.
- [x] `W06.P16.S59` - Record every allowed read-only browser action in centralized external constants and fail tests on new unclassified AEAT actions; `src/aeat/core/external_constants.toml src/aeat/adapters/outbound/aeat`.

## Wave `W07` - secure profile persistence and reload of remote IVA state

This Wave binds live evidence to the active profile's secure storage, then
reloads it into calculation and workflow services. Remote evidence must be
versioned, source-attributed, redacted in diagnostics, and separate from local
recurrence or taxpayer override values.

### Phase `W07.P17` - secure snapshot storage

TODO: Phase intent paragraph required by the convention ADR.

- [x] `W07.P17.S60` - Store filed-history snapshots, wallet observations, auth diagnostics, acquisition manifests, and wallet reconciliation decisions through active or explicitly injected profile-bound secure-object repositories. Completed 2026-06-04: standalone IVA history capture, standalone wallet capture, and combined remote-state capture now all require an active profile storage span before live auth or persistence; `no-active-profile regression tests prove they fail closed before contacting AEAT, and existing injected-repository wallet tests still prove decision persistence stays profile-bound; `src/aeat/application/live src/aeat/application/calculations src/aeat/adapters/persistence/storage`.
- [x] `W07.P17.S61` - Add reload APIs that return latest and historical remote IVA evidence for a profile without requiring a live AEAT login. Completed 2026-05-27: `load_iva_remote_state` reloads stored filed-history state, carry-forward lots, authority decisions, and redacted wallet observation summaries from active-profile secure storage without live AEAT contact. Follow-up 2026-05-27: the same stored-evidence report now includes redacted acquisition-manifest summaries with hashed manifest refs and per-surface typed outcomes, so downstream reconciliation can inspect filed-history, wallet observations, authority decisions, and acquisition attempts through one profile-local backend view; `src/aeat/application/live src/aeat/application/calculations`.
- [x] `W07.P17.S62` - Add secure-storage roundtrip tests for persisted remote IVA evidence using `aeat.tests.secure_sql` and `Settings.aeat_dev_test_database_password`. Completed 2026-05-27: persisted Cl@ve session metadata has isolated runtime-profile storage coverage, and remote IVA filed-history state, wallet observation, and reconciliation decision now roundtrip through profile secure SQL using `aeat.tests.secure_sql` without private taxpayer fixtures; `src/aeat/application/live src/aeat/tests`.
- [x] `W07.P17.S63` - Add privacy tests and hardening proving private live values are not committed to fixtures, plan files, logs, test oracles, or diagnostic dumps. Completed 2026-06-04: wallet diagnostics write redacted structural metadata only, and live IVA acquisition failure contexts now apply diagnostic redaction plus sensitive-key hashing before report, manifest, remote-state reload, and secure SQL persistence; `src/aeat/application/live src/aeat/adapters/outbound/aeat/sede src/aeat/core .vault/plan .vault/audit`.

### Phase `W07.P18` - divergence records and operator review

TODO: Phase intent paragraph required by the convention ADR.

- [x] `W07.P18.S64` - Persist divergence decisions that compare AEAT evidence, filed-history-derived recurrence, local ledger recurrence, and explicit taxpayer override without merging the source values. Completed 2026-06-04: reconciliation tests cover match, wallet-only, wallet-higher, wallet-lower, missing wallet, filed-history-only, stale wallet, and taxpayer override decisions, and secure-storage roundtrip coverage now proves a persisted override decision keeps AEAT wallet, local recurrence, filed-history observation, and taxpayer override authority sources and amounts distinct; `src/aeat/application/calculations src/aeat/application/live`.
- [x] `W07.P18.S65` - Surface blocked, stale, missing-wallet, filed-history-only, and override-required states through workflow/modelo readiness before export or verification. Completed 2026-06-04: focused current-code gates prove localized IVA wallet blocking findings and next actions, verification refusal for filed-history-only decisions, export refusal for filed-history-only decisions, real-engine blocking for wallet-lower, wallet-stale, and missing evidence, and explicit taxpayer override unblocking; `src/aeat/application/modelo src/aeat/application/workflow`.
- [x] `W07.P18.S66` - Add tests for every divergence state using synthetic local ledgers and sanitized official or filed-history shapes, not private taxpayer history. 2026-06-03 adds direct lifecycle authority match, missing-decision, amount-drift, and wallet_only real-engine coverage. Completed 2026-06-04: direct reconciliation covers the full divergence vocabulary, and the real Modelo 303 engine/lifecycle gate now explicitly accepts non-blocking first_period_zero while continuing to block wallet_higher, wallet_lower, wallet_stale, missing, and filed_history_only states; `src/aeat/application/calculations src/aeat/application/modelo`.

## Wave `W08` - multiyear IVA calculation grounding

This Wave proves the local IVA engine can reconstruct compensation and pending
running balances across years, then cross-check those values against persisted
AEAT read-only evidence. AEAT evidence is the binding external state when it is
available; local recurrence is a diagnostic and fallback source, never a silent
replacement for remote state.

### Phase `W08.P19` - multiyear recurrence from production code

TODO: Phase intent paragraph required by the convention ADR.

- [x] `W08.P19.S67` - Add production-code multiyear compensation reconstruction from filed Modelo 303 and Modelo 390 records, including generation, application, remaining balance, and expiry review. Completed 2026-06-04: filed Modelo 303 observations promote compensation period states, secure IVA-history projections expose generated compensation for Modelo 390 binding resolution, the carry-forward report covers generation, application, remaining lots, and four-year expiry review, and filed Modelo 390 casillas 97 and 662 now produce a typed annual summary cross-checked against the 303 carry-forward projection while keeping prior-year lots visible for expiry review but outside the exercise-specific 97/662 comparison; `src/aeat/application/calculations src/aeat/domain/iva_compensation src/aeat/locales`.
- [x] `W08.P19.S68` - Exercise cross-year filing history through repository-backed tests that import production services and do not mirror IVA arithmetic in test code. 2026-05-28 testimonial correction: prior wording claiming repository-backed live captures proved multiyear stored/reloaded history is not accepted as live AEAT evidence. Completed 2026-06-04: the full Modelo 390 previous-filing resolver now merges ordinary calculation observations with secure IVA-history projections for the same Modelo 303 periods, preserves casilla-level provenance, and a repository-backed full-snapshot regression proves annual 303 totals remain `app_filing` while compensation bindings resolve from `aeat_sede_iva_compensation_history`; `separate three-year repository coverage persists sanitized filed Modelo 303 observations through `IvaCompensationHistoryRepository`, reloads them, and lets the production carry-forward projector derive remaining lots. Live cross-year read-only AEAT verification remains open under W06.P15.S56; `src/aeat/application/calculations`.
- [x] `W08.P19.S69` - Verify Modelo 130 relation-regression remains tracked separately and cross-linked, because IRPF quarterly calculations share profile/storage/readiness infrastructure but not IVA compensation authority. Partial 2026-05-27: a full declaration parser gate exposed a separate Modelo 130 binding-resolution regression for casilla 15; `it is queued under the Modelo 130 plan and must not be hidden by the IVA fixes. Reload follow-up 2026-05-27: the reconciliation helper now threads previous-filing values through the explicit registry `binding_values` channel, removes input-only casilla 15 fixtures, and keeps Modelo 130 carry-forward as IRPF/shared-infrastructure evidence rather than IVA compensation authority; `.vault/plan/2026-05-26-modelo-130-relation-regression-plan.md src/aeat/application/filing`.

### Phase `W08.P20` - remote-to-local reconciliation

TODO: Phase intent paragraph required by the convention ADR.

- [x] `W08.P20.S70` - Compare persisted AEAT remote evidence against local recurrence and classify exact match, AEAT higher, AEAT lower, stale remote, missing local state, filed-history-only, override, and wallet_only outcomes. Completed 2026-06-04: production reconciliation coverage classifies match, wallet_higher, wallet_lower, wallet_stale, missing, filed_history_only, override, and wallet_only states; `Modelo 303 engine integration replays persisted decisions and blocks unresolved divergence before revision persistence; export coverage refuses blocked and filed-history-only decisions before file emission, accepts wallet_only through fichero export, records redacted wallet provenance, and supports injected profile-bound decision repositories. Live read-only regression remains open under W06.P15.S56; `src/aeat/application/calculations src/aeat/application/modelo`.
- [x] `W08.P20.S71` - Block Modelo 303 prior-compensation prefill when remote/local divergence is unresolved, and require an explicit persisted decision for any override. Completed 2026-06-04: current Modelo 303 integration coverage proves unpersisted wallet decisions cannot feed the engine, missing wallet evidence blocks until an explicit taxpayer override is persisted, filed-history-only decisions remain blocking, wallet_lower/wallet_higher/wallet_stale/missing decisions block before revision persistence, verification readiness surfaces wallet findings without granting verified-complete, export refuses before file emission, and file action checks the injected profile-bound decision repository before mutation; `src/aeat/application/modelo src/aeat/application/calculations`.
- [x] `W08.P20.S72` - Add focused tests spanning at least three fiscal years and multiple filing periods using sanitized, non-private fixtures and production calculation services. Completed 2026-06-04: `test_three_year_filed_history_repository_projects_compensation_lots` persists sanitized filed Modelo 303 observations across 2024, 2025, and 2026 through the secure IVA compensation history repository, reloads them in filing order, and invokes the production carry-forward projector to derive remaining lots and expiry state without private taxpayer fixtures; `src/aeat/application/calculations src/aeat/application/modelo`.

## Wave `W09` - settings/schema centralization and regression closeout

This Wave closes the hard mandate that AEAT/Sede URLs, route fragments, action
markers, Cl@ve waits, and test database passwords live in centralized settings,
external constants, schemas, or registry TOML/YAML. Tests may assert configured
values, but they must not introduce new source-of-truth literals.

### Phase `W09.P21` - constants inventory and guard

TODO: Phase intent paragraph required by the convention ADR.

- [x] `W09.P21.S73` - Inventory AEAT/Sede host, route, selector, Cl@ve, timeout, wallet, GROI, NIF-IVA, Renta WEB Open, and read-action literals outside centralized settings/config/schema. Completed 2026-06-04: existing centralization tests pass for live Sede executable routes, manual/oracle auxiliary routes, and live action labels; `AST inventory of non-test executable modules found the remaining work in portal catalogue route/host metadata plus one Cl@ve script-body browser-global token, now queued as WALLET-041 for S74/S75; `src/aeat`.
- [x] `W09.P21.S74` - Move remaining source-of-truth literals into centralized external constants, settings, registry TOML/YAML, or typed schema models. 2026-06-03: wallet browser action labels are named Pre303 constants consumed by adapter and tests. Completed 2026-06-04: portal catalogue route paths and filing/censo path-shape rules now live in `external_constants.toml` under the typed `AeatPortalPaths` model, portal entries resolve paths through `portal_path(Portal...)`, `PortalHost` values are stable registry keys instead of hostnames, portal metadata and CLI output resolve hostnames through central AEAT domain settings, the Cl@ve browser-global token is centralized under the Cl@ve surface, and the synthetic justificante generator prints the configured Sede origin and CSV verification URL from external constants; `src/aeat/core src/aeat/domain/portals src/aeat/entrypoints/cli/_app_live.py src/aeat/tests/fixtures/justificantes/_generate.py`.
- [x] `W09.P21.S75` - Add static guard tests that fail on newly hardcoded AEAT/Sede constants outside the central surfaces and accepted comments/docstrings. Partial 2026-05-26: the live Sede executable literal guard now includes `src/aeat/core/config.py`; `follow-up 2026-05-27: the guard now covers NIF-IVA, GROI, and manual-fetch executable files for AEAT host/path/servlet tokens. Completed 2026-06-04: `test_portal_registry_modules_do_not_reintroduce_route_or_host_literals` scans non-test portal modules, excludes docstrings and central resolver helpers, and fails if portal entry modules reintroduce AEAT host literals, `/Sede/`, `/wlpl/`, or root route literals outside centralized `external_constants`; `src/aeat/core/test_external_constants.py src/aeat/domain/portals`.
- [x] `W09.P21.S76` - Ensure all database-backed tests use `Settings.aeat_dev_test_database_password` or `aeat.tests.secure_sql`, never ad hoc password literals. Partial 2026-05-26: `AEAT_DEV_TEST_DATABASE_PASSWORD` is enrolled in `env/.env.example` and Settings alignment tests pass. Completed 2026-06-04: `test_database_operating_passphrases_use_core_test_setting` inventories database-operating tests and fails on literal `passphrase_callback`, literal `AEAT_SECRET_PASSPHRASE`, or literal `aeat_secret_passphrase` overrides; `focused secure-SQL hygiene tests pass, and remaining passphrase literals are classified as non-database master-key/auth/sanitizer unit-test fixtures outside this dev database password step; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/tests/secure_sql.py src/aeat/tests/test_secure_sql.py`.

### Phase `W09.P22` - validation and review closeout

TODO: Phase intent paragraph required by the convention ADR.

- [x] `W09.P22.S77` - Run focused live-wallet hardening gates and record that parser, constants, backend wallet capture, Modelo 303 lifecycle, and export gates pass after removing Modelo 714 registry drift, adding redacted export wallet-decision provenance, wallet_only real-engine coverage, blocked divergence ladder coverage, and full Modelo 303 wallet_only export coverage. Focused gate passes with 123 tests.; `tests src/aeat/adapters/outbound/aeat/sede src/aeat/core src/aeat/application/live src/aeat/application/modelo src/aeat/_data/registry/aeat/modelos/714`.
- [x] `W09.P22.S78` - Keep non-IVA registry drift in scope: 2026-06-03 gates exposed and fixed Modelo 714 Phase-A empty-formulas fragment drift by removing the misleading formulas fragment rather than adding placeholder formulas; `.vault/audit src/aeat/_data/registry/aeat/modelos/714 tests`.
- [x] `W09.P22.S79` - Keep final code review open after 2026-06-03 audit fixed false-zero wallet shell handling, representation-boundary inspection, diagnostic redaction, decision-repository routing, Modelo lifecycle authority matching, centralized wallet action labels, backend test arithmetic, Modelo 714 registry-load drift, redacted export wallet-decision provenance, stale blocked-only helper cleanup, wallet_only real-engine lifecycle coverage, blocked divergence ladder coverage, and full Modelo 303 wallet_only export coverage. Remaining work is tracked in S82 and S83.; `src/aeat/adapters/outbound/aeat/sede src/aeat/application/live src/aeat/application/calculations src/aeat/application/modelo src/aeat/core src/aeat/_data/registry/aeat/modelos/714 .vault/audit`.
- [x] `W09.P22.S80` - Suppress Playwright TargetClosed cancellation noise for bounded live IVA read-surface timeouts. Completed 2026-05-28: combined live IVA remote-state capture now installs a narrow event-loop exception filter while bounded browser read surfaces run; `it suppresses only Playwright `TargetClosedError` contexts caused by cancellation and delegates unrelated loop exceptions. Focused tests prove suppression/delegation, and a read-only live smoke run with an expired session produced a typed Cl@ve timeout without post-command TargetClosed logging. Follow-up 2026-06-02: the filter now also covers Playwright `net::ERR_ABORTED` frame-detach cancellation reports observed during loop shutdown, keeps the handler installed through command loop teardown for the combined read-only capture, and sources the drain delay from centralized settings plus `.env.example`; focused tests and a short read-only live smoke passed without post-command cancellation logging; `src/aeat/application/live src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/core/config.py env/.env.example .vault/audit`.
- [x] `W09.P22.S81` - Add non-private wallet_only export-provenance coverage proving export result payload helpers carry only redacted wallet decision references and no wallet amounts or taxpayer identifiers. Follow-up 2026-06-03: S85 now proves the full Modelo 303 export_modelo_revision happy path against the registry-backed fichero layout.; `src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py src/aeat/domain/calculations/registry`.
- [x] `W09.P22.S82` - Keep opt-in live read-only AEAT wallet and filed-history regression open with operator-observed authentication, redacted aggregate diagnostics, and no live submission or taxpayer-value fixture capture.; `src/aeat/application/live src/aeat/adapters/outbound/aeat/sede src/aeat/entrypoints/cli .vault/audit`.
- [x] `W09.P22.S83` - Add non-private wallet_only local file lifecycle coverage after defining an accepted non-fake local workflow harness that proves the internal Modelo 303 file gate accepts matching wallet authority without contacting AEAT or performing any live submission.; `src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/workflow .vault/audit`.
- [x] `W09.P22.S84` - Broaden non-private divergence ladder coverage for exact match, AEAT higher, AEAT lower, stale remote, local incomplete, filed-history-only, override, and wallet_only using production reconciliation and calculation services.; `src/aeat/application/calculations src/aeat/application/modelo`.
- [x] `W09.P22.S85` - Prove Modelo 303 registry-backed export_layout support with a non-private wallet_only export_modelo_revision happy path that runs create, calculate, verify, export, and redacted event/result provenance without contacting AEAT.; `src/aeat/_data/registry/aeat/modelos/303 src/aeat/application/filing src/aeat/application/modelo src/aeat/entrypoints/cli`.
- [x] `W09.P22.S86` - Fix the live AEAT wallet own-name DialogoRepresentacion dispatcher guard so persisted-session wallet reads can continue only in authenticated own-name mode, then re-run 2026-only and 2022-2026 read-only captures plus redacted profile reload verification.; `src/aeat/adapters/outbound/aeat/sede src/aeat/application/live .vault/exec`.
- [x] `W09.P22.S87` - Fix backend IVA remote-state reload so list/load services open the active profile storage session when invoked outside the CLI root bootstrap, then verify direct backend reload returns redacted aggregate evidence without contacting AEAT.; `src/aeat/application/live src/aeat/adapters/persistence/storage .vault/exec`.

### Phase `W09.P23` - broad test constants remediation

The remaining constants work is test-wide: classify public AEAT/Sede literals in
test expectation data, redaction canaries, remote-state guards, parser fixtures,
and centralization guard tests before the static guard is broadened.

- [x] `W09.P23.S88` - Inventory and migrate remaining test-suite AEAT/Sede host/path literals to central constants or declared exception fixtures before broadening the static guard. 2026-06-04: expanded AST scan after S74 found 224 string constants in test modules and parser expectation fixtures, including remote-state guard canaries, redaction cases, justificante parser text, live-driver tests, and existing centralization guard tokens. Partial 2026-06-04: remote-state guard tests now derive valid AEAT hosts/paths from external constants, deliberate unsafe host/path canaries live in `aeat.tests.aeat_literal_fixtures`, and `test_remote_state_guard_tests_use_declared_aeat_literal_fixtures` prevents that file from reintroducing inline AEAT URLs; `remaining broad inventory was 177 literals outside the declared fixture boundary; `src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/tests/aeat_literal_fixtures.py src/aeat/core/test_external_constants.py`. Partial 2026-06-04: direct Sede/browser/auth executable URL tests now assemble configured origins and paths from `Settings.external_constants()` for declarations register/cotejo URLs, NIF-IVA oracle/auth-gate URLs, site-health probe URLs, persisted auth storage origins, and Playwright certificate origins; the touched subset has no remaining executable AEAT URL/path literals, passes 201 focused tests, and passes Ruff; `src/aeat/adapters/outbound/aeat/sede/test_declarations.py src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py src/aeat/adapters/outbound/aeat/browser/test_site_health.py src/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/auth/test_certificate.py`. Partial 2026-06-04: live application/CLI censo and notification tests plus outbound Sede notification, G313, GROI, parser, observation-store, and browser-error tests now assemble configured origins and paths from `Settings.external_constants()`; the new touched subsets pass 56 application/CLI tests, 46 outbound Sede tests, and Ruff; `src/aeat/application/live/test_censo_snapshot.py src/aeat/application/live/test_notifications.py src/aeat/entrypoints/cli/test_profile_censo_verbs.py src/aeat/entrypoints/cli/test_ratios_verbs.py src/aeat/adapters/outbound/aeat/sede/test_notifications.py src/aeat/adapters/outbound/aeat/sede/test_censo_live.py src/aeat/adapters/outbound/aeat/sede/test_groi_check.py src/aeat/adapters/outbound/aeat/sede/test_parse.py src/aeat/adapters/outbound/aeat/sede/test_observation_store.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/adapters/outbound/aeat/sede/test_groi_check_live.py src/aeat/adapters/outbound/aeat/sede/test_browser_errors.py`. Partial 2026-06-04: live-parity, GROI, and NIF-IVA oracle contract tests now use configured AEAT hosts/paths or declared canaries from `aeat.tests.aeat_literal_fixtures`, and the static guard covers those files; focused guard/parity/oracle tests pass with 125 tests plus Ruff; `src/aeat/domain/calculations/registry/test_live_parity.py src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py src/aeat/tests/aeat_literal_fixtures.py src/aeat/core/test_external_constants.py`. Completed 2026-06-04: broad remediation continued through justificante, portal/manual, registry, live application, workflow, persistence, CLI, and auth tests; missing actual Sede service paths (`r210_simulator_open_ajax`, `borrador_100_detail_template`, `declaracion_consult`, `clave_movil_login`) are now enrolled in the typed external constants schema/TOML, synthetic redaction/storage/parser canaries live only in `aeat.tests.aeat_literal_fixtures`, and the final AST inventory is `TOTAL=0` outside that declared boundary; focused verification passed with Ruff plus 163 justificante tests, 54 portal/manual tests, 125 guard/oracle tests, 123 core/observability/SQL/session tests, 79 app/live/filing tests, 93 runtime-migrated storage tests, 80 CLI tests, 37 Cl@ve tests, and 46 workflow-engine tests; no live AEAT request or write path was executed; `src/aeat/core/external_constants.* src/aeat/tests/aeat_literal_fixtures.py src/aeat`.
- [x] `W09.P23.S89` - Repair locale audit drift for live notification snapshot errors using the locale CLI. Completed 2026-06-04: concrete `application.live.notifications.errors.*` strings were enrolled for `en`, `es`, `ca`, and `hu` with `python -m aeat.locales set`, and locale audit plus locale parity tests pass; `src/aeat/locales`.
- [x] `W09.P23.S90` - Resolve Modelo 100 payments-retentions construct expectation drift by grounding previous-filing membership in dependency classifications and Anexo C carry-forward ownership.; `src/aeat/domain/calculations/registry/test_modelo_100_registry.py .vault/audit`.

## Wave `W10` - live process degradation containment

This wave tracks production-readiness hardening for live AEAT read commands that can overrun, hang, or leave stale child processes after auth timeout, browser cleanup, or live-surface cancellation. It is read-only only: no filing, payment, confirmation, represented-taxpayer selection, or AEAT write path may be executed.

### Phase `W10.P24` - subprocess and browser cleanup containment

Close the degradation where live read commands can outlive their operator-visible timeout because browser cleanup or child process ownership is not bounded. This phase keeps all live runs read-only and records failures separately from successful AEAT evidence.

- [x] `W10.P24.S91` - Bound the live IVA remote-state CLI command with centralized overall timeout settings so auth or cleanup hangs return typed failure instead of leaving stale subprocesses.; `src/aeat/core/config.py src/aeat/entrypoints/cli/_app_live.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/core/test_external_constants.py .vault/audit`.
- [x] `W10.P24.S92` - Add a process-level watchdog and stale-child assertion for live AEAT read CLI commands so outer shell/tool timeouts cannot leave uv, aeat, python, or browser children running. Completed 2026-06-04: combined IVA remote-state capture has a centralized CLI watchdog timeout setting, local tests prove typed timeout classification, subprocess-canary cleanup, and Playwright temp-profile reaping, and the default is corrected to 240000 ms below the 300000 ms live retry outer bound. A later process inventory found a stale `capture-remote-state` command with temp-profile Chrome processes from the same live retry command; `the tree was terminated by exact command/profile match. Later bounded retries returned normally before the outer timeout, and post-run process inventories found no matching capture command, Playwright driver, or temp-profile browser process.; `src/aeat/entrypoints/cli src/aeat/application/live src/aeat/adapters/outbound/aeat/auth tests .vault/audit`.
- [x] `W10.P24.S93` - Repeat read-only live IVA capture after cleanup hardening with explicit stale-process checks before and after the run, recording only redacted aggregate evidence shape. Completed 2026-06-05: after operator-approved Cl@ve auth refreshed the persisted session, the one-shot 2022-2026 command still timed out in `filed_history`, but read-only per-year captures for 2026, 2025, 2024, 2023, and 2022 all succeeded with `auth_reused_persisted_session=True`, filed-history succeeded, wallet/cartera succeeded, and post-run process checks clean. Profile-local secure reload, without live AEAT contact, reports 12 IVA history rows, 8 carry-forward lots, and 2 wallet authority decisions. This closes live evidence acquisition for the requested years via bounded slices; `the one-shot full-range orchestration/watchdog problem remains open under S100.; `src/aeat/application/live src/aeat/adapters/outbound/aeat/sede src/aeat/adapters/outbound/aeat/auth .vault/audit .vault/exec`.
- [x] `W10.P24.S98` - Add lock-safe vaultspec-rag discovery routing or diagnostics for live IVA execution audits so local-store contention is reported as a typed tooling degradation instead of silently blocking required semantic search. Completed 2026-06-05: resident-service routing on port 8766 reports stopped, port-unreachable, MCP search timeout, and crashed-port-silent states as typed diagnostics; `longer service timeout validated a successful code search against the live IVA surfaces. Residual upstream service stability remains noted in the audit.; `src/aeat .vault/audit .vault/exec .vault/plan`.
- [x] `W10.P24.S99` - Prevent persisted Cl@ve session probes from dispatching a fresh target-specific Cl@ve auth request, and add watchdog diagnostics that report local persisted-session state on live IVA command timeout.; `src/aeat/adapters/outbound/aeat/auth src/aeat/entrypoints/cli .vault/audit .vault/exec`.
- [x] `W10.P24.S100` - Complete and live-verify full-range IVA remote-state acquisition so the 2022-2026 command chunks filed-history traversal, scales watchdog budget per covered year, emits one aggregate acquisition report, and leaves no stale processes. Completed 2026-06-05: after fresh Clave auth succeeded, the full-range read-only command reused the persisted session and succeeded for filed-history and wallet/cartera; `aggregate reload reported 12 history rows, 8 carry-forward lots, and 2 authority decisions.; `src/aeat/application/live src/aeat/entrypoints/cli src/aeat/adapters/outbound/aeat/sede .vault/audit .vault/exec`.
- [x] `W10.P24.S101` - Resolve fresh Clave Movil live-auth acquisition when no reusable persisted session exists so S100 full-range IVA capture can be verified without repeated operator-timeout failures. Completed 2026-06-05: after prior diagnostics were classified from operator testimony, the next fresh Clave login succeeded and seeded a reusable session.; `src/aeat/adapters/outbound/aeat/auth src/aeat/application/auth src/aeat/entrypoints/cli .vault/audit .vault/exec .vault/reference`.
- [x] `W10.P24.S102` - Fix auth diagnostics show contract drift so encrypted Clave diagnostic detail renders redacted operator-report commands instead of crashing during S101 phone-state triage.; `src/aeat/application/auth src/aeat/entrypoints/cli .vault/audit .vault/exec`.

## Wave `W11` - live test marker and operational gate separation

This wave separates operator-facing live CLI access from test-only live integration gating. AEAT_LIVE_TESTS_ENABLED remains a test marker/pytest opt-in concern only; operational CLI read commands must rely on profile readiness, auth configuration, read-only remote-state guards, and no-submit safety gates instead of a test environment variable.

### Phase `W11.P25` - live marker inventory and gate separation

Audit all live-read/live-write markers, test hooks, application access gates, and CLI live commands with rg, fd, and vaultspec-rag so pytest integration controls remain test-only while operational read-only CLI commands are not blocked by AEAT_LIVE_TESTS_ENABLED.

- [x] `W11.P25.S94` - Inventory all AEAT_LIVE_TESTS_ENABLED, live_read, live_write, unit, domain, pytest hook, and access-gate usages with rg, fd, and vaultspec-rag semantic search. Completed 2026-06-04: rg/fd inventory maps env ownership to pytest hooks/live-test docs and current production access-gate call sites; `operator live-read gating is now pytest-context-only, live-write remains permanently refused, and RAG lock/timeout degradation is explicitly left open under W10.P24.S98 rather than claimed healthy. Incidental marker-order and corpus-fidelity Ruff regressions were fixed while validating this step.; `pyproject.toml conftest.py src/aeat/tests src/aeat/application src/aeat/adapters src/aeat/entrypoints .vault/audit`.
- [x] `W11.P25.S95` - Remove AEAT_LIVE_TESTS_ENABLED from operator-facing CLI live read commands while preserving profile readiness, auth configuration, read-only remote-state guard, and no-submit safety checks.; `src/aeat/core/access_gate src/aeat/application/live src/aeat/application/auth src/aeat/entrypoints/cli src/aeat/adapters/outbound/aeat .vault/audit`.
- [x] `W11.P25.S96` - Enforce pytest live marker taxonomy so real external-service tests are live_read or live_write, ordinary unit/domain tests never depend on live-test env vars, and live tests are deselected or skipped by default. Completed 2026-06-04: marker integrity rejects executable `AEAT_LIVE_TESTS_ENABLED` runtime access from ordinary unit/domain tests unless the module is live-marked or directly tests the access gate; `cold-process CLI unit helpers no longer set the live-test env var; focused cold-process regressions and full marker integrity pass.; `pyproject.toml conftest.py src/aeat/tests src/aeat/application/conftest.py src/aeat/**/test_*.py .vault/audit`.
- [x] `W11.P25.S97` - Add static guards proving AEAT_LIVE_TESTS_ENABLED is only used by test-selection helpers, pytest hooks, live-test documentation, and not by production CLI/application live read paths.; `src/aeat/tests src/aeat/core src/aeat/application src/aeat/entrypoints src/aeat/adapters .vault/audit`.
