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
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-05-26-securestorage-repair-policy-adr-adjudication-research]]'
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

## Wave `W05` - secure-object reconciliation and calculation confidence

This Wave is the production-readiness follow-through for the critical secure-object
drift discovered during live wallet work. Inventory and redaction are not enough:
operators need a non-destructive reconciliation workflow that separates disposable
test contamination from tax evidence, proves replacement evidence before any
destructive action, and feeds calculation confidence back into ledger, Modelo 303,
Modelo 390, multiyear carry-forward, and AEAT remote-state reconciliation.

No step in this Wave may quarantine, delete, overwrite, or submit live AEAT data
without an explicit preserve-first decision record and verified replacement evidence.

### Phase `W05.P01` - non-destructive unreadable-row attribution

This Phase turns unreadable secure-object rows into safe, operator-facing
metadata: namespace role, IVA relevance, owner semantics, classification counts,
date range, redacted active-profile context, likely origin, and confidence. The
surface must never print payloads, taxpayer ids, expediente ids, profile bucket ids,
wallet amounts, filing identifiers, or natural secure-object keys.

- [x] `W05.P01.S01` - verify `aeat config repair integrity attribution` through public CLI tests with real profile creation and real encrypted unreadable rows; `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`.
- [x] `W05.P01.S02` - classify likely origin for unreadable rows, distinguishing active-profile evidence, stale test-key contamination, legacy migration residue, and unknown preserve-first rows; `src/aeat/application/repair_integrity.py`.
- [x] `W05.P01.S03` - add namespace-level replacement-evidence requirements before a row can be considered remediable; `src/aeat/application/repair_integrity.py`.
- [x] `W05.P01.S04` - expose a summarized attribution view that is usable on hundreds of unreadable rows without dumping every row by default; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W05.P01.S05` - reconcile profile, bucket, repository, secure-object, calculation-binding, and wallet-reconciliation terminology in a binding ADR for the remaining repair and calculation-confidence wave; `.vault/adr/2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr.md`.

### Phase `W05.P02` - preserve-first remediation decision ladder

This Phase adds a decision workflow for what to do with degraded rows. The default
state is preserve; any quarantine/rebuild action must be dry-run first and must
reference replacement evidence, owner approval, and affected calculation domains.

- [x] `W05.P02.S01` - model repair decisions as durable, profile-local, non-destructive records with preserve/quarantine/rebuild/export-required outcomes; `src/aeat/application/repair_integrity.py`.
- [x] `W05.P02.S02` - add `aeat config repair plan` as a dry-run remediation planner that cannot mutate state; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W05.P02.S03` - require explicit replacement evidence for ledger, invoices, Modelo work units, filing drafts, justificantes, filed declarations, wallet observations, and wallet reconciliation decisions before quarantine is allowed; `src/aeat/application/repair_integrity.py`.
- [x] `W05.P02.S04` - keep destructive quarantine disabled for critical submission receipt and filing-history namespaces unless an engineer-only override is later specified in a separate ADR; `src/aeat/application/repair_integrity.py`.

### Phase `W05.P03` - calculation confidence and cross-domain blocking

This Phase connects repair integrity to the IVA calculation pipeline. The CLI must
tell the operator whether ledger evidence, periodic Modelo 303 forms, annual Modelo
390 summaries, multiyear carry-forward lots, and AEAT remote-state reconciliation
are trustworthy under the current storage health.

- [ ] `W05.P03.S01` - add a calculation-confidence report that maps degraded namespaces to ledger, periodic IVA, annual IVA, multiyear carry-forward, and AEAT remote-state authority domains; `src/aeat/application/repair_integrity.py`.
- [ ] `W05.P03.S02` - block or warn calculation/export surfaces when degraded namespaces affect their evidence domain and no verified replacement evidence exists; `src/aeat/application/modelo, src/aeat/entrypoints/cli`.
- [ ] `W05.P03.S03` - add persona-driven CLI tests for ledger to Modelo 303 to Modelo 390 to multiyear carry-forward under degraded secure-object state; `src/aeat/entrypoints/cli`.
- [ ] `W05.P03.S04` - verify AEAT wallet and filed-history reconciliation remains separate from local recurrence and explicit taxpayer overrides when local evidence health is degraded; `src/aeat/application/calculations`.

### Phase `W05.P04` - testimonial-driven acceptance loop

This Phase keeps operators in the loop. Personas must use the official CLI, report
whether they understand the risk and next action, and drive follow-up tasks until
the repair/reconciliation workflow is safe enough for production tax work.

- [ ] `W05.P04.S01` - run an accountant persona through the attribution and remediation-plan CLI without deleting anything; `.vault/audit`.
- [ ] `W05.P04.S02` - run a multiyear IVA reviewer persona through degraded-state carry-forward and AEAT reconciliation confidence output; `.vault/audit`.
- [ ] `W05.P04.S03` - run a live-wallet reviewer persona through read-only repair attribution before any live wallet or filed-history capture is attempted; `.vault/audit`.
- [ ] `W05.P04.S04` - promote repeated testimonial friction into concrete W05 implementation findings and review them after each fix; `.vault/plan, .vault/audit`.

## Wave `W06` - adverse-condition backend hardening

This Wave turns the secure-object and profile/bucket ADRs into failure-mode
contracts. The backend must behave deterministically when the active pointer is
missing, the manifest is malformed, the database route falls back to root storage,
rows are encrypted under stale keys, readable rows fail envelope validation, and
external evidence is incomplete. The expected behavior is preserve-first
diagnostics, calculation confidence degradation, and explicit blocking where tax
outputs would otherwise look filing-ready.

### Phase `W06.P01` - storage routing and active-profile fault matrix

This Phase verifies profile, bucket, pointer, manifest, session, and repository
routing under broken or ambiguous local state.

- [ ] `W06.P01.S01` - add an adverse-condition matrix for missing active pointer, malformed manifest, locked profile, stale bucket session, explicit database URL, and root fallback database routing; `src/aeat/application, src/aeat/adapters/persistence/storage`.
- [ ] `W06.P01.S02` - block profile-bound writes when routing resolves to the root fallback database outside explicit test/diagnostic isolation; `src/aeat/core/config.py, src/aeat/adapters/persistence/storage/sql`.
- [ ] `W06.P01.S03` - add real repository tests proving bucket-attached repositories cannot silently cross-write between two profile UUIDs; `src/aeat/application/user_profile, src/aeat/tests`.
- [ ] `W06.P01.S04` - add repair diagnostics that separate pointer/manifest/session faults from secure-object decryptability faults; `src/aeat/application/diagnostics.py`.

### Phase `W06.P02` - encrypted row integrity and envelope-contract validation

This Phase verifies the backend never treats decryptability alone as enough.
Readable rows must still satisfy the owning repository envelope contract.

- [ ] `W06.P02.S01` - require repair summaries to include unreadable-row origin, replacement-evidence requirements, and readable-row envelope-contract drift counts; `src/aeat/application/repair_integrity.py`.
- [ ] `W06.P02.S02` - add domain-envelope integrity coverage for ledger, invoices, Modelo work units, filing drafts, filed declarations, wallet observations, auth sessions, profile records, and bucket events; `src/aeat/application/test_repair_integrity.py`.
- [ ] `W06.P02.S03` - add relational SQL integrity checks for non-secure-object tables that feed calculation or filing state; `src/aeat/application/diagnostics.py`.
- [ ] `W06.P02.S04` - add test hygiene guards that fail when `EphemeralMasterKeyProvider` writes through default repositories without isolated database routing; `src/aeat/tests`.

### Phase `W06.P03` - degraded-evidence calculation behavior

This Phase verifies calculation behavior when required evidence is missing,
unreadable, stale, contradictory, or lower-confidence.

- [ ] `W06.P03.S01` - add calculation-confidence contracts for degraded ledger and invoice evidence before Modelo 303 calculation/export; `src/aeat/application/modelo, src/aeat/application/aggregation`.
- [ ] `W06.P03.S02` - add calculation-confidence contracts for degraded Modelo 303 history before Modelo 390 and multiyear carry-forward use; `src/aeat/application/calculations, src/aeat/application/modelo`.
- [ ] `W06.P03.S03` - add contradiction tests for wallet-vs-local recurrence and filed-history-vs-calculation observations under stale or unreadable local evidence; `src/aeat/application/calculations`.
- [ ] `W06.P03.S04` - ensure every blocked degraded-evidence calculation surfaces a next action that points to repair attribution or replacement evidence, not a generic failure; `src/aeat/entrypoints/cli, src/aeat/core/errors`.

### Phase `W06.P04` - live-read safety under adverse browser state

This Phase verifies live AEAT read paths remain read-only when AEAT presents
unexpected forms, representation gates, empty-wallet shells, session expiry, or
changed page structure.

- [ ] `W06.P04.S01` - add parser fixtures for changed wallet shells, empty tables, interstitials, session expiry, and representation prompts that all fail closed without submission; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [ ] `W06.P04.S02` - add Cl@ve Móvil adverse-state tests for cancellation, wrong provider page, timeout, representation continuation, and verification-code display without identity leakage; `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`.
- [ ] `W06.P04.S03` - prove live-read guards reject every POST or click path not classified in external constants, including newly discovered AEAT controls; `src/aeat/core/external_constants.toml, src/aeat/adapters/outbound/aeat`.
- [ ] `W06.P04.S04` - add a live-disabled smoke harness that exercises the wallet path to the safety boundary without a real AEAT session; `src/aeat/entrypoints/cli`.

## Wave `W07` - complete IVA backend end-to-end verification

This Wave proves the robust backend as an integrated pipeline rather than a set
of isolated fixes. The verified path is ledger and invoice evidence to periodic
IVA, yearly IVA summary, cross-year carry-forward, AEAT remote-state
reconciliation, filing/export blocking, and replayable audit provenance.

### Phase `W07.P01` - source mesh completeness for IVA domains

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W07.P01.S01` - map every IVA-relevant registry binding source to an enrolled source resolver, explicit manual input, or explicit not-yet-calculable diagnostic; `src/aeat/application/aggregation, src/aeat/domain/calculations/registry`.
- [ ] `W07.P01.S02` - verify ledger, invoice, usage ratio, prorrata, OSS/IOSS, previous filing, wallet, and profile sources emit typed observations and source fingerprints; `src/aeat/application/aggregation, src/aeat/application/calculations`.
- [ ] `W07.P01.S03` - reject manual overrides against every source-owned IVA binding and bound casilla, not only ledger-owned bindings; `src/aeat/application/modelo/_actions.py`.

### Phase `W07.P02` - replayable IVA calculation regression matrix

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W07.P02.S01` - build a real-repository regression matrix for ordinary IVA, reverse charge, exempt activity, prorrata, recargo, OSS/IOSS, correction, negative result, compensation application, and zero-activity periods; `src/aeat/application/modelo`.
- [ ] `W07.P02.S02` - verify Modelo 390 annual summary from four produced Modelo 303 calculations without test-side arithmetic mirrors; `src/aeat/domain/calculations/registry, src/aeat/application/modelo`.
- [ ] `W07.P02.S03` - verify cross-year carry-forward lots, expiry, local recurrence, wallet authority, and explicit override replay from persisted evidence only; `src/aeat/application/calculations`.

### Phase `W07.P03` - export and filing-readiness gates

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W07.P03.S01` - ensure export refuses blocked wallet decisions, degraded source confidence, unreadable submission-history evidence, and incomplete registry calculation closure; `src/aeat/application/modelo/_export.py`.
- [ ] `W07.P03.S02` - ensure verify/readiness/overview consume the same canonical projection and cannot disagree on filing readiness under degraded state; `src/aeat/application/state_projection.py, src/aeat/entrypoints/cli`.
- [ ] `W07.P03.S03` - add redaction contracts for every CLI output that mentions repair, wallet history, filing evidence, auth diagnostics, or profile context; `src/aeat/entrypoints/cli`.

### Phase `W07.P04` - adverse-condition persona regression

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W07.P04.S01` - run an autónomo persona through a clean end-to-end IVA workflow and record success criteria, commands, and remaining friction; `.vault/audit`.
- [ ] `W07.P04.S02` - run an accountant persona through degraded evidence, repair attribution, confidence output, and blocked export; `.vault/audit`.
- [ ] `W07.P04.S03` - run a live-wallet reviewer persona through read-only safety boundaries and wallet/filer reconciliation output without live submission; `.vault/audit`.
- [ ] `W07.P04.S04` - promote persona findings into concrete implementation tasks until no critical or high severity workflow gaps remain; `.vault/plan, .vault/audit`.

## Wave `W08` - release readiness and evidence closure

This Wave closes the backend as production-ready evidence: focused code review,
vault traceability, safety-gate verification, and an explicit list of deferred
non-blocking follow-ups.

### Phase `W08.P01` - safety and privacy release gate

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W08.P01.S01` - run a focused security/privacy code review over live AEAT, repair, auth diagnostics, profile routing, and wallet history surfaces; `.vault/audit`.
- [ ] `W08.P01.S02` - verify no CLI output leaks taxpayer ids, profile UUIDs, wallet amounts, filing identifiers, private natural keys, or auth context outside deliberate detail commands; `src/aeat/entrypoints/cli`.
- [ ] `W08.P01.S03` - verify no live AEAT mutation path is reachable from wallet capture, Cl@ve verification, auth diagnostics, or filing-readiness commands; `src/aeat/adapters/outbound/aeat`.

### Phase `W08.P02` - quality-gate convergence

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W08.P02.S01` - run focused pytest suites for repair, storage routing, live wallet, auth, source mesh, Modelo 303, Modelo 390, export, and state projection; `tests`.
- [ ] `W08.P02.S02` - run focused ruff checks for every touched backend, CLI, and test module; `src/aeat`.
- [ ] `W08.P02.S03` - run vault frontmatter, link, body-link, plan status, and plan check gates, recording known plan-format exceptions separately; `.vault`.

### Phase `W08.P03` - final testimonial and documentation closure

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W08.P03.S01` - collect final persona testimonials against clean, degraded, and live-read-safety workflows and record success criteria satisfaction; `.vault/audit`.
- [ ] `W08.P03.S02` - update operator-facing repair and IVA wallet safety documentation through the vault documentation workflow; `.vault`.
- [ ] `W08.P03.S03` - write the final live IVA compensation wallet backend readiness summary with residual risks and natural follow-up work; `.vault/exec`.

## Wave `W09` - SecureStorage repair and recovery policy governance

This Wave makes the repair/recovery work explicitly cross-domain. The accepted
SecureStorage production hardening ADR is the core architecture decision; the
wallet repair work must converge with config repair, bucket lifecycle,
custody/recovery, secure persistence enforcement, imports, exports, ledger,
invoices, Modelo state, filing history, wallet evidence, auth sessions, bucket
events, and remote mirror state. The result must not be an IVA-wallet-only
hotpatch: every repair or recovery surface must declare its policy, mutation
authority, redaction contract, source-of-truth relationship, and test evidence.

No step in this Wave may introduce live AEAT submission, silent key minting,
root fallback production writes, destructive bucket deletion, destructive
quarantine, or source-evidence overwrite without an accepted ADR and an explicit
operator confirmation path.

### Phase `W09.P01` - ADR coverage and policy map closure

This Phase reconciles the accepted ADR chain into one executable policy map for
SecureStorage repair and recovery.

- [x] `W09.P01.S01` - produce an ADR coverage matrix for SecureStorage repair/recovery across config repair, bucket maintenance, profile lifecycle, custody/recovery, secure persistence, ledger, invoices, imports, exports, Modelo state, filing history, wallet evidence, auth sessions, bucket events, and remote mirror state; `.vault/audit`.
- [x] `W09.P01.S02` - decide whether the accepted SecureStorage production hardening ADR fully governs repair/recovery policy mechanisms or whether a focused ADR amendment is required; `.vault/adr, .vault/research`.
- [x] `W09.P01.S03` - add a namespace-policy map that records owner domain, bucket scope, sensitivity class, repair policy, recovery policy, mutation authority, export/import behavior, retention/legal note, and calculation-confidence impact for every governed namespace; `src/aeat/application/repair_integrity.py, src/aeat/adapters/persistence/storage`.
- [x] `W09.P01.S04` - add a policy-coverage gate that fails when a new repair, recovery, import, export, or bucket command lacks an ADR-linked namespace/domain policy; `tests, .vault`.

### Phase `W09.P02` - CLI repair and recovery surface convergence

This Phase verifies that operator-facing commands all speak the same safe policy
language and remain thin wrappers over backend policy services.

- [ ] `W09.P02.S01` - audit `aeat config repair`, `aeat config bucket`, profile import/export, ledger import/export, invoice import/export, Modelo export, auth diagnostics, wallet history, and live-read commands for dry-run, `--yes`, redaction, next-action, and mutation-policy consistency; `.vault/audit, src/aeat/entrypoints/cli`.
- [ ] `W09.P02.S02` - centralize mutation-policy descriptors for repair/recovery/import/export commands so CLI handlers cannot invent command-local safety semantics; `src/aeat/application, src/aeat/entrypoints/cli`.
- [ ] `W09.P02.S03` - add real CLI privacy and non-mutation tests for bucket browse/search/export/import/delete, profile switch/import/export, ledger/invoice import/export, Modelo export, and repair plan output; `src/aeat/entrypoints/cli`.
- [ ] `W09.P02.S04` - ensure every warn/fail recovery diagnostic points to a concrete safe command or a dead-end report path without exposing profile UUIDs, natural keys, taxpayer ids, filing ids, wallet amounts, or auth context; `src/aeat/application/diagnostics.py, src/aeat/core/errors`.

### Phase `W09.P03` - backend policy enforcement across repositories

This Phase moves the policy from documentation and CLI copy into shared backend
contracts.

- [ ] `W09.P03.S01` - enforce the SecureStorage runtime/repository boundary for profile-bound production writes and classify any direct `SecureObjectRepository` construction as infrastructure, repair, test isolation, or violation; `src/aeat/adapters/persistence/storage, src/aeat/application`.
- [ ] `W09.P03.S02` - block or degrade reads from unregistered namespaces, unreadable rows, envelope-contract drift, root fallback routing, stale sessions, and malformed bucket manifests before data reaches source resolvers; `src/aeat/application, src/aeat/adapters/persistence/storage`.
- [ ] `W09.P03.S03` - implement domain repair policies for transactions, ledger ratios, invoices, imports, exports, Modelo work units, filing drafts, submitted declarations, justificantes, wallet observations, wallet reconciliation decisions, auth sessions, profile records, and bucket events; `src/aeat/application/repair_integrity.py`.
- [ ] `W09.P03.S04` - add adverse-condition repository tests proving policy enforcement under two profiles, locked custody, expired session, explicit database URL, unreadable rows, readable-but-invalid envelopes, and partial namespace coverage; `tests`.

### Phase `W09.P04` - custody, bucket import/export, and remote mirror recovery

This Phase covers recovery paths that are not merely row-level repair.

- [ ] `W09.P04.S01` - verify passphrase/recovery-code/keychain custody failures fail closed without silent key minting and with repair output that names safe recovery actions; `src/aeat/adapters/persistence/storage, src/aeat/entrypoints/cli`.
- [ ] `W09.P04.S02` - verify bucket export/import/restore preserves encrypted payloads, namespace policies, checksums, revision lineage, and profile identity boundaries without plaintext leakage; `src/aeat/application/bucket_maintenance, src/aeat/adapters/persistence/storage`.
- [ ] `W09.P04.S03` - verify remote mirror recovery handles partial upload, partial download, stale manifest, missing escrow, and namespace mismatch as degraded recovery states rather than implicit success; `src/aeat/adapters/outbound, src/aeat/adapters/persistence/storage`.
- [ ] `W09.P04.S04` - connect retention/legal diagnostics to recovery policy so local loss of ledger, invoices, working calculations, filed receipts, or supporting documents is surfaced as compliance-relevant risk; `src/aeat/application/repair_integrity.py, src/aeat/application/diagnostics.py`.

### Phase `W09.P05` - cross-domain persona testimonials

This Phase checks the complete repair/recovery policy through the official CLI
with personas who operate outside the wallet-only path.

- [ ] `W09.P05.S01` - run an autónomo persona through ledger/invoice import, degraded storage attribution, repair plan, and blocked Modelo export without deleting or submitting anything; `.vault/audit`.
- [ ] `W09.P05.S02` - run an accountant persona through bucket export/import, filed-history recovery, justificante evidence review, and annual/multiyear confidence output; `.vault/audit`.
- [ ] `W09.P05.S03` - run a storage-recovery persona through locked custody, wrong passphrase, missing recovery material, malformed bucket manifest, and remote mirror partial recovery; `.vault/audit`.
- [ ] `W09.P05.S04` - promote repeated persona friction into concrete implementation tasks until no critical or high severity cross-domain repair/recovery gaps remain; `.vault/plan, .vault/audit`.

## Wave `W10` - codebase convention regrounding and duplication hardening

This Wave explicitly re-grounds the wallet, SecureStorage, repair, and IVA
calculation work in repository-wide conventions. The purpose is not local
polish: every backend hardening step must reinforce the established contracts
for localised user-facing text, central AEAT exception hierarchy, observable
exception handling, centralized settings, non-tautological tests, and shared
models/enums rather than creating slice-specific patterns.

The Wave is cross-domain and applies to ledger, invoices, periodic IVA forms,
yearly IVA summaries, multiyear carry-forward, SecureStorage repair/recovery,
auth sessions, CLI commands, export/import surfaces, and AEAT remote-state
reconciliation. Any discovered exception must be tracked in audit with severity
and routed either to an immediate fix, an ADR amendment requirement, or an
explicit deferred step.

### Phase `W10.P01` - exceptions and user-facing localisation

This Phase audits and hardens the exception hierarchy and user-facing error
text. Exceptions must derive from the central AEAT base hierarchy and rendered
operator messages must flow through registered locale keys or direct `tr(...)`
calls at the boundary.

- [x] `W10.P01.S01` - add a central `SecureStorageError` base that reuses the existing `AeatError` registry pattern, make storage/bucket errors inherit from it, and prove representative SecureStorage messages render from locale keys; `src/aeat/adapters/persistence/storage, src/aeat/core/errors/registry, src/aeat/locales`.
- [x] `W10.P01.S02` - audit every production exception class still deriving from bare `Exception`/`ValueError` without an accepted non-AEAT rationale, classify violations, and migrate or document each exception family; `src/aeat, .vault/audit`.
- [x] `W10.P01.S03` - audit user-facing CLI, application, adapter, and domain error construction for raw positional strings that bypass `translated_message`, registered message keys, or direct `tr(...)`; `src/aeat, .vault/audit`.
- [x] `W10.P01.S04` - add or extend static gates so new user-facing error messages cannot bypass locale keys and new AEAT exception families cannot bypass the registry; `src/aeat/core/errors, src/aeat/entrypoints/cli, src/aeat/locales`.

### Phase `W10.P02` - exception swallowing and diagnostic observability

This Phase makes swallowed exceptions visible. Every caught exception that is
not deliberately converted into a typed AEAT error, returned diagnostic, or
control-flow value must leave at least a debug-level breadcrumb without leaking
secrets.

- [ ] `W10.P02.S01` - run Spark code discovery across `except` blocks, `contextlib.suppress`, broad catches, and fallback paths, producing a severity-ranked swallowing inventory; `.vault/audit`.
- [ ] `W10.P02.S02` - ensure broad catches in SecureStorage, repair, auth, live-read, IVA calculation, import/export, and CLI boundaries log debug diagnostics or convert to typed AEAT errors with redacted context; `src/aeat`.
- [ ] `W10.P02.S03` - add tests that exercise representative swallowed-exception paths and assert safe diagnostics, typed errors, or explicit control-flow outcomes without mocks or tautological expectations; `tests`.

### Phase `W10.P03` - centralized settings and environment boundary

This Phase prevents ad-hoc environment wrangling. Production code must route
AEAT configuration through the centralized settings/core definitions unless an
accepted ADR names a narrower bootstrap exception.

- [ ] `W10.P03.S01` - inventory production `os.environ`, `os.getenv`, direct env key literals, path fallback, and configuration parsing outside `aeat.core.config` and approved bootstrap/test boundaries; `.vault/audit`.
- [ ] `W10.P03.S02` - migrate SecureStorage, auth, live-read, repair, import/export, and IVA calculation configuration reads to centralized `Settings`, core constants, or typed settings helpers; `src/aeat/core, src/aeat/application, src/aeat/adapters`.
- [ ] `W10.P03.S03` - add a focused static guard that fails when new production AEAT env reads bypass the centralized settings boundary; `tests`.

### Phase `W10.P04` - shared enums, models, and duplication control

This Phase audits duplicated domain concepts and reuses existing core enums,
shared dataclasses, and Pydantic models before adding new local structures.

- [ ] `W10.P04.S01` - run Spark code discovery for duplicate enum literals, pydantic-shaped records, command policy records, storage namespace records, IVA authority/status records, and ad-hoc state dictionaries; `.vault/audit`.
- [ ] `W10.P04.S02` - consolidate duplicated SecureStorage, repair, wallet, IVA source-confidence, filing-readiness, import/export, and live-state models into shared domain/application models where the existing architecture permits; `src/aeat`.
- [ ] `W10.P04.S03` - add regression tests proving migrated consumers share the canonical enum/model definitions and cannot silently drift; `tests`.

### Phase `W10.P05` - non-tautological verification and persona feedback

This Phase keeps verification honest. Tests must import production code,
exercise real behavior, avoid mirrored calculation engines, avoid superficial
assertions, and collect CLI persona testimonials where workflow friction affects
architecture.

- [ ] `W10.P05.S01` - audit IVA, SecureStorage, repair, export, import, and CLI tests for mirrored business logic, fake/stub shortcuts, monkeypatched production behavior, skipped/xfail gates, and assertions that only restate implementation literals; `.vault/audit`.
- [ ] `W10.P05.S02` - replace high-risk tautological tests with real repository, registry, CLI, or fixture-backed behavior tests that expose calculation and safety regressions; `tests`.
- [ ] `W10.P05.S03` - run official `uv run vaultspec-core ...` checks and focused pytest/ruff gates after each convention-hardening slice, recording known plan-format exceptions separately; `.vault/exec`.
- [ ] `W10.P05.S04` - brief Spark/persona agents for CLI testimonials covering clean IVA operation, degraded SecureStorage, wrong custody, import/export recovery, and remote-state reconciliation without live AEAT mutation; `.vault/audit`.

### Phase `W10.P06` - test database contamination and fixture review

This Phase keeps the live IVA and SecureStorage confidence work grounded in
repository-wide test conventions. Database-backed tests must not write into the
active operator profile, must not rely on ad-hoc passphrase literals, and must
use real production repositories against isolated storage. The review is part of
the original wallet/IVA objective: local calculations cannot be trusted against
AEAT-maintained state if the test suite can contaminate or silently reuse the
wrong secure-object database.

- [x] `W10.P06.S01` - add the canonical development/test database password as a core Settings field and constant, including the env schema entry; `src/aeat/core/config.py, env/.env.example`.
- [x] `W10.P06.S02` - route the shared secure SQL helper through the canonical dev/test database password and isolated database override; `src/aeat/tests/secure_sql.py`.
- [x] `W10.P06.S03` - migrate the immediate database-backed secure-storage and custody tests that carried ad-hoc passphrase literals to the shared core setting; `src/aeat/adapters/persistence/storage, src/aeat/core, src/aeat/entrypoints/cli`.
- [ ] `W10.P06.S04` - review every pending EphemeralMasterKeyProvider plus SQL-backed repository test exception and either isolate it with the shared fixture or classify the remaining gap with owner, severity, and source domain; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py, .vault/audit`.
- [x] `W10.P06.S05` - add a static guard preventing new database-operating tests from introducing local passphrase/password literals or default SQL writes without explicit isolation; `tests`.
- [x] `W10.P06.S06` - run the contamination-sensitive matrix before and after fixture migration, proving no active-profile secure-object row count changes and no live taxpayer history is used as a test oracle; `tests, .vault/exec`.
- [x] `W10.P06.S07` - fix the repair privacy and custody CLI fixtures now classified by the hygiene guard or focused verification, resolving the profile-create bootstrap/runtime mismatch without reintroducing unsecured or explicit-root database contamination; `src/aeat/entrypoints/cli/test_repair_privacy_contract.py, src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py`.
- [ ] `W10.P06.S08` - drain the remaining active EphemeralMasterKeyProvider plus SQL-backed repository exception list in small real-behavior isolation batches, keeping the allow-list stale-entry guard at zero; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py, tests`.
- [ ] `W10.P06.S09` - produce the remaining secure-storage test exception classification audit with owner, severity, and source-domain metadata kept out of source code; `.vault/audit, src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.

S08 progress checkpoint, 2026-05-26: the active exception list is down to one file after removing stale default-repository coverage from calculation observations, Modelo export, Modelo 303 IVA wallet engine integration, runtime-migrated repositories, profile/declaration binding tests, profile aggregate repository tests, and finca SQL-session repository tests. The remaining file is `src/aeat/entrypoints/cli/test_workflow_surface.py`; focused execution shows a real CLI/profile bootstrap regression where profile-create flows cannot yet be exercised cleanly under the hardened profile-bucket storage route, so this stays open for S09 classification and follow-up repair.
