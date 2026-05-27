---
tags:
  - '#plan'
  - '#live-iva-compensation-wallet'
date: '2026-05-19'
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

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

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

- [x] `W05.P13.S45` - Add redacted live-auth preflight diagnostics for active profile identity, configured DNI/NIE presence, support-number presence, certificate provider state, Cl@ve preference, and timeout. Partial 2026-05-26: existing Cl@ve diagnostic payload fields for identity/config/certificate state are now exposed through the application diagnostic read model, including `prefer_non_qr` and `timeout_ms`; CLI preflight rendering remains open. Completed 2026-05-27: `build_live_auth_preflight_report` now exposes a redacted application-owned preflight report, and IVA live CLI pull/capture-history commands render provider, active-profile, identity-alignment, route-mode, timeout, support-number presence, certificate state, and persisted-session presence to stderr before invoking live auth. Review follow-up 2026-05-27: the same preflight now runs before filed-history list/capture/capture-sources, DEHu notifications capture, and expedientes capture live-read entrypoints; `src/aeat/application/auth src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W05.P13.S46` - Classify and log the selected Cl@ve route as push, QR, non-QR fallback, certificate, or unknown without swallowing browser errors. Partial 2026-05-26: application diagnostics now classify captured AEAT auth URLs against centralized `external_constants.toml` Cl@ve/Sede routes; driver-side start logging already records selected `auth_mode`; richer outcome taxonomy remains open. Completed 2026-05-27: Cl@ve fresh-login attempt context now records `auth_route`, encrypted diagnostics surface that route, and the provider start log records mode, route, identity kind, identity alignment, profile-tax-id presence, and headless state without raw identifiers; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/application/auth`.
- [x] `W05.P13.S47` - Enforce the operator-facing auth wait window from centralized settings, with a production default not exceeding 120 seconds for Cl@ve approval waits; `src/aeat/core/config.py src/aeat/adapters/outbound/aeat/auth`.
- [ ] `W05.P13.S48` - Add real-behavior diagnostic tests that use production auth diagnostics and redaction logic without private taxpayer fixtures, fakes, stubs, or monkeypatched browser behavior. Partial 2026-05-26: `src/aeat/application/auth/test_diagnostics.py` now drives the real secure-object diagnostic read model with sanitized payloads and centralized AEAT route constants; live-driver regression coverage remains open; `src/aeat/application/auth src/aeat/adapters/outbound/aeat/auth`.
  - 2026-05-26 live evidence: `test_clave_movil_playwright_entrypoint_reaches_live_selector` reached the live AEAT Cl@ve selector. Fresh login attempts reached the non-QR Cl@ve route and emitted encrypted diagnostics, but timed out waiting for post-auth landing. Redacted diagnostics show configured identity kind `NIE`, profile tax id present, identity alignment `matches`, `prefer_non_qr=True`, `timeout_ms=120000`, and route `clave_movil_non_qr_request`.

### Phase `W05.P14` - live-auth regression taxonomy
Convert the current ambiguous live-auth failures into typed outcomes so no 403,
missing prompt, QR fallback, timeout, wrong identity, or DOM drift is treated as
a generic unavailable state.

- [ ] `W05.P14.S49` - Introduce typed live-auth acquisition outcomes for no-prompt, operator-timeout, QR-required, certificate-required, wrong-identity, AEAT-403, DOM-drift, and authenticated. Partial 2026-05-26: `LiveIvaAcquisitionFailureMode` and `classify_live_iva_acquisition_failure` now map Cl@ve and Sede adapter exceptions into application-level outcomes; acquisition result wrapping and authenticated-success records remain open. Partial 2026-05-27: persisted Cl@ve session loading now accepts provider-specific encrypted metadata by narrowing it to provider-neutral identity, provider kind, authentication time, and idle deadline before parsing; structural diagnostics confirmed a reused, unexpired profile session without a fresh operator prompt; `src/aeat/adapters/outbound/aeat/auth src/aeat/application/auth src/aeat/application/live`.
- [ ] `W05.P14.S50` - Propagate live-auth outcomes through CLI and backend result models using locale keys for operator-facing text; `src/aeat/entrypoints/cli/_app_live.py src/aeat/locales`.
- [ ] `W05.P14.S51` - Persist redacted live-auth diagnostic events in the current profile's secure storage route when a profile runtime is available; `src/aeat/application/live src/aeat/adapters/persistence/storage`.
- [ ] `W05.P14.S52` - Add regression tests proving 403 and missing-prompt outcomes are not collapsed into success, zero-balance, or generic unavailable results. Partial 2026-05-26: application-level taxonomy tests now cover no-prompt, operator-timeout, QR-required, wrong-identity, AEAT-403, and DOM-drift classification; end-to-end wallet/history result tests remain open; `src/aeat/adapters/outbound/aeat/auth src/aeat/adapters/outbound/aeat/sede`.
  - 2026-05-26 live evidence: the live auth test now opens profile-bound secure storage before reading/writing encrypted Cl@ve session state. Previous no-active-bucket-session failures were local test setup defects and are fixed in `src/aeat/adapters/outbound/aeat/auth/test_clave_movil_live.py`. Remaining failures are auth-completion timeouts on AEAT Cl@ve non-QR landing and must remain typed failures until an operator-confirmed approval lands on the target page.

## Wave `W06` - read-only Sede acquisition backend

This Wave makes live AEAT acquisition a backend capability first. CLI commands
may invoke it, but the authoritative behavior belongs to application services
and outbound Sede adapters. All live interactions remain read-only and must stop
before filing, payment, representation, or form-confirmation submission.

### Phase `W06.P15` - filed-history pull and wallet pull services
Implement a single read-only acquisition service that can pull filed-history
evidence and, where AEAT allows it, wallet/cartera evidence for the authenticated
profile.

- [ ] `W06.P15.S53` - Build a backend read-only acquisition orchestration that authenticates once, fetches filed Modelo history across requested years, attempts wallet/cartera read, and returns typed evidence plus typed failures. Partial 2026-05-27: the backend live capture path reused the persisted Cl@ve session and fetched Modelo 303 filed-history evidence year by year through secure profile storage; direct wallet/cartera acquisition remains unresolved and must keep typed failure semantics. Partial 2026-05-27 follow-up: `capture_iva_remote_state` now acquires one session and reports filed-history and wallet/cartera as separate typed surfaces in `IvaRemoteStateAcquisitionReport`; `src/aeat/application/live`.
- [ ] `W06.P15.S54` - Keep wallet/cartera direct-read failures distinct from filed-history success so a 403 wallet outcome does not discard usable filed-history evidence. Blocker: direct wallet/cartera live acquisition is not yet accepted as reliable production evidence and must remain fail-closed until the live route yields parseable wallet evidence or a legally grounded no-wallet surface. Partial 2026-05-27: filed-history capture succeeded independently for past-year Modelo 303 history while the direct wallet surface remains a separate fail-closed open issue. Partial 2026-05-27 follow-up: combined acquisition report composition preserves filed-history success when wallet/cartera returns typed `AEAT_403`; `src/aeat/application/live src/aeat/adapters/outbound/aeat/sede`.
- [ ] `W06.P15.S55` - Add multi-year filed-history parsing coverage using sanitized official or committed corpus evidence only, never the operator's private tax history as a fixture. Partial 2026-05-27: production parsing was corrected against live filed-history shapes, but no private live values were copied into tests; remaining fixture work must use sanitized official or synthetic non-private evidence only; `src/aeat/adapters/outbound/aeat/sede`.
- [ ] `W06.P15.S56` - Add an opt-in live read-only test path that requires operator authentication and records only redacted diagnostics and aggregate evidence shape, not private taxpayer values. Partial 2026-05-27: read-only live capture was exercised for 2022 through 2026 and recorded only structural counts; 2022, 2023, and 2024 each promoted filed Modelo 303 compensation history, while 2025 and 2026 completed with no promoted IVA compensation rows; `src/aeat/adapters/outbound/aeat/sede/test_*_live.py`.
### Phase `W06.P16` - representation gate and read-only action boundary
The authenticated user is acting for the authenticated profile unless an
explicit representative mode is implemented later. Read-only acquisition may
identify the authenticated taxpayer where AEAT requires that to reach a read
surface, but it must not submit representation, filing, payment, or confirmation
intent.

- [ ] `W06.P16.S57` - Rework representation-gate handling so own-profile read-only identity confirmation is allowed only when the guard classifies it as authentication/read navigation, not filing or representative submission; `src/aeat/adapters/outbound/aeat/sede src/aeat/domain/calculations/registry/_remote_state_guard.py`.
- [ ] `W06.P16.S58` - Add guard tests for own-profile read navigation versus represented-taxpayer, filing, payment, and confirmation submissions; `src/aeat/adapters/outbound/aeat/sede src/aeat/domain/calculations/registry`.
- [ ] `W06.P16.S59` - Record every allowed read-only browser action in centralized external constants and fail tests on new unclassified AEAT actions; `src/aeat/core/external_constants.toml src/aeat/adapters/outbound/aeat`.
## Wave `W07` - secure profile persistence and reload of remote IVA state

This Wave binds live evidence to the active profile's secure storage, then
reloads it into calculation and workflow services. Remote evidence must be
versioned, source-attributed, redacted in diagnostics, and separate from local
recurrence or taxpayer override values.

### Phase `W07.P17` - secure snapshot storage
- [ ] `W07.P17.S60` - Store filed-history snapshots, wallet observations, auth diagnostics, and acquisition manifests through active-profile `StorageRuntime` repositories. Partial 2026-05-27: filed-history observations, derived IVA compensation calculation observations, wallet observations, and wallet reconciliation decisions persist through active-profile secure storage and reload after capture. Partial 2026-05-27 follow-up: combined live IVA remote-state acquisition now persists a redacted encrypted profile-local acquisition manifest with per-surface success/failure status, typed wallet/history outcomes, reloaded history counts, and decision references; review fixes require active-profile runtime storage, omit local output paths from persisted manifests, and align object keys with the centralized full SHA-256 namespace grammar; CLI/backend auth-event linkage remains open; `src/aeat/application/live src/aeat/adapters/persistence/storage`.
- [x] `W07.P17.S61` - Add reload APIs that return latest and historical remote IVA evidence for a profile without requiring a live AEAT login. Completed 2026-05-27: `load_iva_remote_state` reloads stored filed-history state, carry-forward lots, authority decisions, and redacted wallet observation summaries from active-profile secure storage without live AEAT contact. Follow-up 2026-05-27: the same stored-evidence report now includes redacted acquisition-manifest summaries with hashed manifest refs and per-surface typed outcomes, so downstream reconciliation can inspect filed-history, wallet observations, authority decisions, and acquisition attempts through one profile-local backend view; `src/aeat/application/live src/aeat/application/calculations`.
- [x] `W07.P17.S62` - Add secure-storage roundtrip tests for persisted remote IVA evidence using `aeat.tests.secure_sql` and `Settings.aeat_dev_test_database_password`. Completed 2026-05-27: persisted Cl@ve session metadata has isolated runtime-profile storage coverage, and remote IVA filed-history state, wallet observation, and reconciliation decision now roundtrip through profile secure SQL using `aeat.tests.secure_sql` without private taxpayer fixtures; `src/aeat/application/live src/aeat/tests`.
- [ ] `W07.P17.S63` - Add privacy tests proving private live values are not committed to fixtures, plan files, logs, or test oracles. Partial 2026-05-27: this slice deliberately stores live values only in the profile's secure store and uses structural counts in the plan; follow-up 2026-05-27: live IVA wallet code/tests and matching vault plan/audit artefacts are covered by a static valid-looking taxpayer identifier guard, with broader runtime log scanning still open; reload follow-up 2026-05-27: exact leaked operator NIE/name markers were removed from sanitizer tests, Sede fixtures, user-profile/live-storage tests, and older vault notes, and the source/vault scan is clean outside the local private env file; `src/aeat/application/live src/aeat/adapters/outbound/aeat src/aeat/adapters/inbound .vault/plan .vault/audit`.
### Phase `W07.P18` - divergence records and operator review
- [ ] `W07.P18.S64` - Persist divergence decisions that compare AEAT evidence, filed-history-derived recurrence, local ledger recurrence, and explicit taxpayer override without merging the source values. Partial 2026-05-27: filed-history-derived Modelo 303 recurrence now preserves the persisted observation source kind and direct wallet/cartera absence is classified as explicit `filed_history_only` authority rather than generic local recurrence; persistence/readiness integration remains open; `src/aeat/application/calculations`.
- [ ] `W07.P18.S65` - Surface blocked, stale, missing-wallet, filed-history-only, and override-required states through workflow/modelo readiness before export or verification. Partial 2026-05-27: Modelo 303 calculation now treats `filed_history_only`, `wallet_missing`, and stale-wallet fallback decisions as blocking evidence states; direct wallet/cartera match, wallet-only evidence, or explicit taxpayer override remain the non-blocking paths. Follow-up 2026-05-27: Modelo verification and export now have fallback-specific coverage proving persisted `filed_history_only` decisions block readiness/export before file emission; workflow-level readiness wording remains open; `src/aeat/application/modelo src/aeat/application/workflow`.
- [ ] `W07.P18.S66` - Add tests for every divergence state using synthetic local ledgers and sanitized official/filed-history shapes, not private taxpayer history. Partial 2026-05-27: focused calculation tests now cover `filed_history_only` classification and production IVA-history repository fallback source preservation without private taxpayer fixtures; follow-up 2026-05-27: Modelo 303 engine integration now proves missing wallet/cartera plus persisted AEAT filed-history recurrence blocks automatic prefill, and a separate explicit taxpayer override is required before the real engine can use that fallback amount; follow-up 2026-05-27: verification/export tests now assert `filed_history_only` is surfaced as blocking readiness, not just a calculation exception; full workflow readiness coverage remains open; `src/aeat/application/calculations src/aeat/application/modelo`.
## Wave `W08` - multiyear IVA calculation grounding

This Wave proves the local IVA engine can reconstruct compensation and pending
running balances across years, then cross-check those values against persisted
AEAT read-only evidence. AEAT evidence is the binding external state when it is
available; local recurrence is a diagnostic and fallback source, never a silent
replacement for remote state.

### Phase `W08.P19` - multiyear recurrence from production code
- [ ] `W08.P19.S67` - Add production-code multiyear compensation reconstruction from filed Modelo 303 and Modelo 390 records, including generation, application, remaining balance, and expiry review. Partial 2026-05-27: filed Modelo 303 compensation observations now promote semantic and numeric casilla identifiers into compensation history, including derived end-of-period compensation availability; Modelo 390 integration and expiry review remain open; `src/aeat/application/calculations src/aeat/domain/iva`.
- [ ] `W08.P19.S68` - Exercise cross-year filing history through repository-backed tests that import production services and do not mirror IVA arithmetic in test code. Partial 2026-05-27: repository-backed live captures proved multiyear stored/reloaded history across 2022, 2023, and 2024; non-private three-year regression coverage remains open; `src/aeat/application/calculations`.
- [x] `W08.P19.S69` - Verify Modelo 130 relation-regression remains tracked separately and cross-linked, because IRPF quarterly calculations share profile/storage/readiness infrastructure but not IVA compensation authority. Partial 2026-05-27: a full declaration parser gate exposed a separate Modelo 130 binding-resolution regression for casilla 15; it is queued under the Modelo 130 plan and must not be hidden by the IVA fixes. Reload follow-up 2026-05-27: the reconciliation helper now threads previous-filing values through the explicit registry `binding_values` channel, removes input-only casilla 15 fixtures, and keeps Modelo 130 carry-forward as IRPF/shared-infrastructure evidence rather than IVA compensation authority; `.vault/plan/2026-05-26-modelo-130-relation-regression-plan.md src/aeat/application/filing`.
### Phase `W08.P20` - remote-to-local reconciliation
- [ ] `W08.P20.S70` - Compare persisted AEAT remote evidence against local recurrence and classify exact match, AEAT higher, AEAT lower, stale remote, local incomplete, and override-required outcomes. Partial 2026-05-27: live filed-history evidence can now be promoted into persisted calculation observations for comparison; follow-up 2026-05-27: AEAT filed-history-only recurrence is now a distinct blocking fallback state when wallet/cartera is unavailable, while full persisted remote/local ladder coverage remains open; `src/aeat/application/calculations`.
- [ ] `W08.P20.S71` - Block Modelo 303 prior-compensation prefill when remote/local divergence is unresolved, and require an explicit persisted decision for any override. Partial 2026-05-27: unresolved fallback states now block prefill in the Modelo 303 engine; an explicit taxpayer override decision can unblock the same filed-history fallback amount while preserving separate authority sources. Follow-up 2026-05-27: persisted `filed_history_only` fallback decisions now have explicit verification/export readiness tests; broader workflow readiness coverage remains open; `src/aeat/application/modelo src/aeat/application/calculations`.
- [ ] `W08.P20.S72` - Add focused tests spanning at least three fiscal years and multiple filing periods using sanitized, non-private fixtures and production calculation services; `src/aeat/application/calculations src/aeat/application/modelo`.
## Wave `W09` - settings/schema centralization and regression closeout

This Wave closes the hard mandate that AEAT/Sede URLs, route fragments, action
markers, Cl@ve waits, and test database passwords live in centralized settings,
external constants, schemas, or registry TOML/YAML. Tests may assert configured
values, but they must not introduce new source-of-truth literals.

### Phase `W09.P21` - constants inventory and guard
- [ ] `W09.P21.S73` - Inventory AEAT/Sede host, route, selector, Cl@ve, timeout, wallet, GROI, NIF-IVA, Renta WEB Open, and read-action literals outside centralized settings/config/schema. Partial 2026-05-27: executable-source scan found residual NIF-IVA auth diagnostic endpoint descriptors and the manuals Biblioteca root path outside the central registry; broader portal/path metadata inventory remains open; `src/aeat`.
- [ ] `W09.P21.S74` - Move remaining source-of-truth literals into `src/aeat/core/external_constants.toml`, `Settings`, registry TOML/YAML, or typed schema models as appropriate. Partial 2026-05-26: status-reader defaults now source from external constants, portal host resolution no longer falls back to hardcoded subdomain origins, the GROI form-action guard derives from the centralized oracle URL, and live filed-history tests now source declaration-register URLs from `external_constants`. Partial 2026-05-27: Modelo 303 submitted-file layout corrections for optional pages, casilla export references, and older page-03 fallback behavior are stored in registry TOML or parser schema logic rather than test-local constants. Follow-up 2026-05-27: manuals Biblioteca root and NIF-IVA/GROI auth diagnostic endpoint descriptors now live in `external_constants.toml`; broader literal inventory remains open; `src/aeat/core src/aeat/_data/registry src/aeat/domain/calculations/registry`.
- [ ] `W09.P21.S75` - Add static guard tests that fail on newly hardcoded AEAT/Sede constants outside the central surfaces and accepted comments/docstrings. Partial 2026-05-26: the live Sede executable literal guard now includes `src/aeat/core/config.py`; follow-up 2026-05-27: the guard now covers NIF-IVA, GROI, and manual-fetch executable files for AEAT host/path/servlet tokens; broader portal/path metadata guard remains open; `src/aeat/tests src/aeat/core`.
- [ ] `W09.P21.S76` - Ensure all database-backed tests use `Settings.aeat_dev_test_database_password` or `aeat.tests.secure_sql`, never ad hoc password literals. Partial 2026-05-26: `AEAT_DEV_TEST_DATABASE_PASSWORD` is enrolled in `env/.env.example` and Settings alignment tests pass; residual database-backed tests still need inventory; `src/aeat/tests`.
### Phase `W09.P22` - validation and review closeout
- [ ] `W09.P22.S77` - Run focused live-auth, Sede read-only, secure-storage, Modelo 303/390, Modelo 130 relation, and constants-guard test gates. Partial 2026-05-27: focused ruff and pytest gates passed for persisted session metadata, live filed-capture compensation history, and Modelo 303 submitted-file fallback behavior; the broader declaration parser gate still exposes the queued Modelo 130 binding regression. Partial 2026-05-27 follow-up: live application acquisition taxonomy, wallet backend, and combined remote-state report tests pass; follow-up 2026-05-27: the affected live/modelo gate exposed and fixed missing Modelo 303 extraction-profile `verification_source` registry provenance for the two IVA wallet-backed revisions; follow-up 2026-05-27 reload: focused Modelo 303 wallet export/readiness tests, Renta Art. 84 scenario tests, user-profile schema/profile-family tests, touched-file ruff checks, and privacy scans pass after privacy and registry-drift repairs; reload follow-up 2026-05-27: registry-backed filing helper, calculation summary, and reconciliation tests pass with Modelo 130 previous-filing bindings routed through `binding_values`, reconciliation providers built from each draft snapshot ref, and direct provider checks for Modelos 180, 200, 111, 123, and 130 pass; `tests src/aeat/_data/registry`.
- [ ] `W09.P22.S78` - Persist review findings for any discovered non-IVA problems and keep them in scope until assigned to an owning plan row. Partial 2026-05-27: Modelo 130 casilla 15 binding-resolution failure is explicitly tracked as separate IRPF/shared-infrastructure work and must remain in scope outside the IVA compensation authority path. Follow-up 2026-05-27: Modelo 303 engine integration exposed a ledger application export-contract regression; the missing `_actions` rule/bulk classification exports and `_result` helper were restored so calculation preflight can import, and the ledger CLI `--from-csv` / `ledger rule` surface now passes its focused regression gate with rule/manual provenance projected in list output. Follow-up 2026-05-27 reload: wallet readiness tests no longer carry DNI/NIE-shaped synthetic taxpayer data, and shared Renta registry/profile-schema drift discovered by the IVA verification gate is recorded in `RELOAD-008`; reload follow-up 2026-05-27: exact operator-identity leaks are recorded in `RELOAD-009`, and the reconciliation gate's Modelo 130 previous-filing projection plus Modelo 180 legal-ref blockers are recorded in `RELOAD-010`; reload follow-up 2026-05-27: RELOAD-010 is resolved for the active reconciliation surface, with Modelo 180/200 provider drift rechecked as clear in the current tree; `.vault/audit .vault/plan src/aeat/application/filing src/aeat/application/ledger src/aeat/entrypoints/cli src/aeat/_data/registry`.
- [ ] `W09.P22.S79` - Run final code review before treating live IVA grounding as production-ready. Partial 2026-05-27: focused review of stored remote IVA reload and ledger regression fixes found and closed two HIGH issues: rule-apply failures now surface instead of being counted as no-match, and wallet secure-storage tests no longer use valid-looking taxpayer identifiers; `.vault/audit`.
