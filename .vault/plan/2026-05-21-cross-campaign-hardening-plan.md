---
tags:
  - '#plan'
  - '#cross-campaign-hardening'
date: '2026-05-21'
tier: L2
related:
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
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

# `cross-campaign-hardening` cross-campaign hardening rollout

### Phase `P01` - CRITICAL remediation

Eliminate the eight CRITICAL findings: provenance loss, persistence
roundtrip gaps, blank CLI refusals, and a domain→adapter import.

- [x] `P01.S01` - CALC-1: restore casilla provenance on `amend_modelo_revision` (dd10fd70d) - `_amendment_observations` helper, 16 amend-flow tests green; `src/aeat/application/modelo`.
- [x] `P01.S02` - EXIM-1: add `casilla_provenance` to `ModeloDraft`; `src/aeat/domain/filing src/aeat/application/filing src/aeat/application/modelo`.
- [x] `P01.S03` - PERS-1: strict `SecureObjectRecord` roundtrip test with six non-default fields and on-disk-mutation anti-tautology; `src/aeat/adapters/persistence`.
- [x] `P01.S04` - PERS-2: strict `SecretRecord` roundtrip witness and anti-tautology on the JSON index; `src/aeat/adapters/persistence`.
- [x] `P01.S05` - PERS-3: `BucketManifest` fail-closed on an absent `status` key in TOML reads; `src/aeat/adapters/persistence`.
- [x] `P01.S06` - WCLI-2: apoderado-check refusal to `resolve_error_message` and WCLI-1 contested disposition; `src/aeat/entrypoints/cli`.
- [x] `P01.S07` - XDOM-1: export `SecureBoundRepository` from the envelope public surface; `src/aeat/adapters/persistence`.

### Phase `P02` - HIGH: CLI error-rendering localization

Close the message-key-loss pattern across the remaining CLI handlers.

- [x] `P02.S08` - WCLI-3: `_modelo.py` `typer.BadParameter(str(exc))` sites to `resolve_error_message`; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `P02.S09` - WCLI-4: `_app_live.py` narrow the broad exception and use `resolve_error_message`; `src/aeat/entrypoints/cli/_app_live.py`.

### Phase `P03` - HIGH: hexagonal / private-import cleanup

Restore the hexagonal boundary at five application↔adapter and
application↔domain private-import sites.

- [x] `P03.S10` - XDOM-2: route workflow `_engine.py` adapter imports through Protocol seams or shared types; `src/aeat/application/workflow`.
- [x] `P03.S11` - XDOM-3: import `FiledDeclaracionObservation` from the public `sede` surface; `src/aeat/adapters/outbound/aeat/sede`.
- [x] `P03.S12` - XDOM-4: promote `_normalise_key` to the `domain.profile` public surface; `src/aeat/domain/profile`.
- [x] `P03.S13` - XDOM-5: add public accessor for `_profile_binding_selectors` on `domain.user_profile`; `src/aeat/domain/user_profile`.
- [x] `P03.S14` - XDOM-6: add public export for the auth-diagnostics namespace constant; `src/aeat/application/auth`.

### Phase `P04` - HIGH: binding-source retirement

Close the `"invoice"` source-kind drift.

- [x] `P04.S15` - BIND-1: close the `"invoice"` wildcard in `resolve_counterpart_binding_row_values`; `src/aeat/domain/calculations/registry`.
- [ ] `P04.S16` - BIND-2: snapshot-build rejection of retired `source = "invoice"` bindings; `src/aeat/domain/calculations/registry`.

### Phase `P05` - HIGH: provenance + roundtrip coverage

Provenance on import; snapshot validation; and the persistence
roundtrip / anti-tautology gaps.

- [ ] `P05.S17` - CALC-2: `import_external_filing` builds registry-sourced `CasillaObservation` rows; `src/aeat/application/filing`.
- [ ] `P05.S18` - CALC-3: snapshot validator asserts every `input_kind="bound"` casilla has a binding definition; `src/aeat/domain/calculations/registry`.
- [ ] `P05.S19` - PERS-4: unify `object_key` type across record/write and add identity roundtrip test; `src/aeat/adapters/persistence`.
- [ ] `P05.S20` - PERS-5: `RecoveryRecord` envelope-file roundtrip and base64 anti-tautology; `src/aeat/adapters/persistence`.
- [ ] `P05.S21` - PERS-6: `SecureObjectMetadata` peek consistency test and anti-tautology; `src/aeat/adapters/persistence`.
- [ ] `P05.S22` - PERS-7: concurrent-write serialization test for `SecureObjectRepository`; `src/aeat/adapters/persistence`.
- [x] `P05.S23` - EXIM-2: fichero-BOE RESERVED-field anti-tautology proof (ed4b529ac) - corrupt-the-literal test, 9 roundtrip tests green; `src/aeat/adapters/outbound/aeat/export/_formats`.
- [ ] `P05.S24` - EXIM-3: asset-ledger delete-field anti-tautology proof; `src/aeat/application/modelo`.

### Phase `P06` - HIGH: export coverage + Google Sheets guard

Lock export-adjacent coverage after the critical provenance path lands.

- [ ] `P06.S25` - EXIM-4: document and test Google Sheets as a one-way export mirror; `src/aeat/adapters/outbound/google`.
- [ ] `P06.S26` - EXIM-5: export tests for no-layout modelos, `binding_rows`, and computed fields; `src/aeat/application/filing`.

### Phase `P07` - MED cluster

Close medium-severity calculation, persistence, CLI, boundary, export, and binding findings.

- [ ] `P07.S27` - CALC-4/CALC-5/CALC-6: defence-in-depth note, typed per-source binding selectors, and formula-runtime test replacement; `src/aeat/domain/calculations/registry`.
- [ ] `P07.S28` - PERS-8/PERS-9: TOML datetime ISO inspection and `EncryptionMetadata` AAD missing-vs-empty; `src/aeat/adapters/persistence`.
- [ ] `P07.S29` - WCLI-5/WCLI-6: `BucketEventType` enum-error `tr()` and `InvoiceLinkError` disposition; `src/aeat/entrypoints/cli`.
- [ ] `P07.S30` - XDOM-7/XDOM-8/XDOM-9: `LedgerTransactionPayload` model, public URL-validation helper, and public `sede` export; `src/aeat/application src/aeat/adapters/outbound/aeat/sede`.
- [ ] `P07.S31` - EXIM-6: verify verdict reports reserved-field unchecked casillas; `src/aeat/application/filing`.
- [ ] `P07.S32` - BIND-3/BIND-4/BIND-5: numeric profile-binding Decimal-channel test, free-form source-kind cleanup, and estimacion-directa disposition; `src/aeat/domain/calculations/registry`.

### Phase `P08` - LOW cluster

Close lower-severity typing, persistence, boundary, and binding-stability findings.

- [ ] `P08.S33` - CALC-7: tighten `ModeloInputsProviderProtocol.load_inputs` return type; `src/aeat/application/modelo`.
- [ ] `P08.S34` - PERS-10/PERS-11: KDF-param witnesses and `SecureObjectNamespaceIntegrity` test; `src/aeat/adapters/persistence`.
- [ ] `P08.S35` - XDOM-11/XDOM-12: re-point registry private imports, export `RegistrySnapshotRef`, and add non-303 period-binding tests; `src/aeat/domain/calculations/registry src/aeat/application/modelo`.
- [ ] `P08.S36` - BIND-8/BIND-9: stabilise the `test_invoice_bindings` fixture filter and atribucion/refund source-kind disposition; `src/aeat/domain/calculations/registry`.

### Phase `P09` - carried-over coordinator items (Axis G)

Pre-existing coordinator task-list items folded into this rollout.

- [ ] `P09.S37` - GEN-1 task 501: wire the live G313 Playwright driver actual fetch path; `src/aeat/adapters/outbound/aeat`.
- [ ] `P09.S38` - GEN-2 task 506: triage the discovery-swarm legacy/shim inventory into fixes; `.vault/audit src/aeat`.
- [ ] `P09.S39` - GEN-3 task 517: non-303 period-token test coverage for `_resolve_declaration_period_inputs`; `src/aeat/application/modelo`.
- [ ] `P09.S40` - GEN-4 task 518: profile UUID-vs-label delegated to the `cli-workflow-redesign` campaign; `.vault/plan`.
- [ ] `P09.S41` - GEN-5 task 520: CLI UX polish cluster cross-check against the `cli-workflow-redesign` bug-inventory clusters D/E; `.vault/audit src/aeat/entrypoints/cli`.
- [ ] `P09.S42` - GEN-6 task 521: estimacion-directa profile auto-resolution disposition; `src/aeat/domain/calculations/registry`.

### Phase `P10` - verification + persona-testimonial re-audit

Run final gates and re-audit the operator-facing scenarios after all finding rows close.

- [ ] `P10.S43` - run the full gate set: locale parity, CLI suite, registry suite, and touched-domain suites; `src/aeat`.
- [ ] `P10.S44` - persona-testimonial pass over the hardened CLI and backend; `.vault/audit src/aeat`.
- [ ] `P10.S45` - fold any testimonial regressions into a follow-up wave and re-run affected gates; `.vault/plan src/aeat`.
