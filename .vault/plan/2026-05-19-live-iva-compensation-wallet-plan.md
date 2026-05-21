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

- [x] `W01.P02.S01` - implement `fetch_iva_compensation_wallet` as a read-only Sede adapter; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [x] `W01.P02.S02` - add parser coverage from captured wallet HTML fixtures; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [x] `W01.P02.S03` - add opt-in live smoke coverage gated by `AEAT_LIVE_TESTS_ENABLED`; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py`.

### Phase `W01.P03` - persist wallet evidence

This Phase stores wallet observations so calculation prefill can use the latest
authenticated AEAT evidence without requiring a live login on every calculation.

- [x] `W01.P03.S01` - add encrypted persistence support for wallet observations; `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`.
- [x] `W01.P03.S02` - add repository roundtrip tests for wallet observations; `src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py`.
- [x] `W01.P03.S03` - add encrypted persistence support for wallet reconciliation decisions; `src/aeat/application/calculations/_observations_repository.py`.
- [x] `W01.P03.S04` - add backend workflow entry point for operator-approved wallet pull; `src/aeat/application/live/__init__.py`.

### Phase `W01.P04` - reconcile and prefill Modelo 303

This Phase connects wallet observations to the Modelo 303 prior compensation
binding and blocks silent divergence.

- [x] `W01.P04.S01` - implement local recurrence extraction for comparison without selecting the effective value; `src/aeat/application/calculations/_binding_prefill.py`.
- [x] `W01.P04.S02` - implement wallet, override, local recurrence authority selection and blocking divergence statuses; `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `W01.P04.S03` - consume only non-blocking reconciliation decisions for Modelo 303 prior compensation prefill; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P04.S04` - prevent automatic output when the wallet reconciliation decision is blocked; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P04.S05` - add divergence scenario tests for match, AEAT-higher, AEAT-lower, stale wallet, missing wallet, and explicit taxpayer override; `src/aeat/application/calculations/test_iva_wallet_reconciliation.py`.
- [x] `W01.P04.S06` - run wallet, Modelo 303, Modelo 390, and relation-regression focused suites together; `tests`.

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

### Phase `W02.P01` - fail closed before wallet or representation form actions

This Phase hardens the live wallet reader around AEAT form boundaries. The
driver may authenticate and navigate to read surfaces, but it must refuse
unclassified wallet execute shells, unrecognized empty-wallet pages, and
representation choices that would post taxpayer or represented-party intent to
AEAT. Any wallet read-query exception must be explicit in the remote-state guard
and verified by parser fail-closed tests.

- [x] `W02.P01.S01` - block the wallet execute gate by static HTML inspection without running page JavaScript; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [x] `W02.P01.S02` - remove any wallet POST allowance from the read guard and prove wallet POST is rejected; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [x] `W02.P01.S03` - reject no-table wallet shells instead of interpreting them as zero-balance observations; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [x] `W02.P01.S04` - fail closed on AEAT representation-gate submission in wallet capture and Cl@ve verification; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py, src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.

### Phase `W02.P02` - audit every live AEAT browser action

This Phase turns live browser actions into an explicit allow-list contract.
Every click, fill, evaluate, navigation, and POST-capable interaction is
classified before use so new AEAT automation cannot enter the codebase without
an audited read-only or authentication-only safety label.

- [x] `W02.P02.S01` - enumerate every live AEAT click, fill, evaluate, navigation, and POST-capable browser action across Sede/auth adapters; `src/aeat/adapters/outbound/aeat`.
- [x] `W02.P02.S02` - classify each action as authentication-only, read-only navigation, diagnostic cleanup, or forbidden live submission; `src/aeat/adapters/outbound/aeat`.
- [x] `W02.P02.S03` - move accepted action markers into external constants and guard policies; `src/aeat/core/external_constants.toml, src/aeat/domain/calculations/registry/_remote_state_guard.py`.
- [x] `W02.P02.S04` - add tests that fail when new live AEAT form-submission paths are introduced without explicit safety classification; `src/aeat/adapters/outbound/aeat`.

## Wave `W03` - complete IVA calculation engine verification

This Wave expands the wallet work into the broader IVA calculation engine:
ledger evidence must flow into periodic IVA forms, annual summaries, cross-year
carry-forward state, and AEAT remote-state reconciliation without duplicated
business logic or silent authority inversions.

### Phase `W03.P01` - ledger-to-periodic IVA calculation chain

This Phase proves ledger evidence reaches periodic Modelo 303 calculations
through production aggregation and registry bindings. The tests must exercise
ordinary IVA, special regimes, reverse-charge and adjustment cases without
duplicating Modelo 303 arithmetic inside assertions.

- [x] `W03.P01.S01` - verify ledger aggregation inputs for ordinary IVA, recargo equivalencia, exenciones, OSS/IOSS, intra-community operations, and adjustments; `src/aeat/application/aggregation, src/aeat/domain/iva`.
- [x] `W03.P01.S02` - verify Modelo 303 periodic casilla bindings consume registry formulas and ledger observations rather than mirrored test arithmetic; `src/aeat/application/modelo, src/aeat/domain/calculations/registry`.
- [x] `W03.P01.S03` - add traceable calculation tests from ledger rows to Modelo 303 outputs for positive, negative, zero, and compensation-applied periods; `src/aeat/application/aggregation, src/aeat/application/modelo`.

### Phase `W03.P02` - yearly IVA summary forms

This Phase verifies the annual IVA summary path against the quarterly Modelo
303 evidence it summarizes. Modelo 390 coverage must reconcile annual fields
to produced quarterly observations and block unsupported regimes instead of
silently inferring values outside the registry.

- [x] `W03.P02.S01` - verify Modelo 390 annual fields reconcile against four Modelo 303 periods, including casillas `97` and `662`; `src/aeat/domain/calculations/registry, src/aeat/application/modelo`.
- [x] `W03.P02.S02` - verify annual summary behavior for regimes represented in the ledger catalogue and identify unsupported regimes as blocking gaps rather than inferred formulas; `src/aeat/domain/iva, src/aeat/domain/calculations/registry`.
- [x] `W03.P02.S03` - add cross-form tests that compare annual totals to periodic observations without reimplementing form business logic in tests; `src/aeat/application/modelo, src/aeat/domain/calculations/registry`.

### Phase `W03.P03` - cross-year and multiyear carry-forward tracking

This Phase models IVA compensation as dated carry-forward lots rather than a
single same-year aggregate. Source period, age, applied amount, remaining
balance, expiry state, and AEAT/local divergence must remain visible across
fiscal years.

- [x] `W03.P03.S01` - model carry-forward age, source period, applied amount, remaining amount, and expiry review state across fiscal years; `src/aeat/application/calculations, src/aeat/domain/iva`.
- [x] `W03.P03.S02` - enforce LIVA art. 99 four-year compensation-window policy from dated evidence rather than same-year recurrence only; `src/aeat/application/calculations, src/aeat/domain/calculations/registry`.
- [x] `W03.P03.S03` - add multiyear tests for generation year, application year, expiry boundary, AEAT wallet divergence, and local filed-history fallback; `src/aeat/application/calculations, src/aeat/application/modelo`.

### Phase `W03.P04` - AEAT remote-state reconciliation ladder

This Phase establishes the authority ladder for remote-state values. AEAT
wallet evidence, local recurrence, filed-history observations, and taxpayer
overrides stay separate, and only persisted non-blocking decisions may affect
calculation, verification, or export.

- [x] `W03.P04.S01` - require persisted non-blocking reconciliation decisions before remote-state values affect form outputs; `src/aeat/application/calculations, src/aeat/application/modelo`.
- [x] `W03.P04.S02` - keep AEAT wallet evidence, local recurrence, filed-history observations, and explicit taxpayer overrides as separate authority sources; `src/aeat/application/calculations`.
- [x] `W03.P04.S03` - surface blocked reconciliation states through CLI/workflow before any calculation/export path can proceed; `src/aeat/entrypoints/cli, src/aeat/application/filing`.

## Wave `W04` - CLI operator-persona testimonial verification

This Wave turns CLI usage into first-class evidence. Subagents/personas operate
the official CLI, record what they attempted, what worked, where they hesitated,
and which outputs were insufficient for safe tax work. No persona may enter real
taxpayer secrets or perform live AEAT submission.

### Phase `W04.P01` - persona briefs

This Phase defines the operator personas used to test the wallet and IVA
pipeline through the official CLI. Each persona receives a bounded task brief
that forbids live AEAT submission and asks for practical friction, safety, and
calculation-surface feedback.

- [x] `W04.P01.S01` - brief a first-run autónomo persona to create/switch a profile, import or enter ledger evidence, calculate a Modelo 303 period, and report friction; `.vault/audit`.
- [x] `W04.P01.S02` - brief a returning accountant persona to inspect filed-history/ledger state, calculate four quarters, prepare Modelo 390, and report reconciliation gaps; `.vault/audit`.
- [x] `W04.P01.S03` - brief a live-wallet reviewer persona to run the official live wallet CLI path only up to the fail-closed safety boundary, verify no AEAT filing/payment/represented-taxpayer choice is submitted beyond the guarded wallet read query, and report the operator experience; `.vault/audit`.
- [x] `W04.P01.S04` - brief a multiyear compensation reviewer persona to exercise cross-year carry-forward scenarios and report whether the CLI exposes source-period age and authority decisions clearly; `.vault/audit`.

### Phase `W04.P02` - testimonial capture and audit integration

This Phase converts persona CLI testimony into implementation evidence.
Commands, redacted outputs, hesitation points, and safety observations are
captured in the audit log, then repeated friction is promoted into concrete
follow-up tasks and reviewed after each fix.

- [x] `W04.P02.S01` - capture persona commands, redacted outputs, friction points, and safety observations in audit notes; `.vault/audit`.
- [x] `W04.P02.S02` - convert repeated persona friction into concrete implementation tasks with severity and file/module ownership; `.vault/plan, .vault/audit`.
- [x] `W04.P02.S03` - run code-review after each persona-driven implementation step and append findings to the wallet/IVA audit log; `.vault/audit`.

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
