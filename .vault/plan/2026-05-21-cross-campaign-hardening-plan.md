---
tags:
  - '#plan'
  - '#cross-campaign-hardening'
date: '2026-05-21'
modified: '2026-05-21'
tier: L2
related:
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
  - '[[2026-06-04-cross-campaign-hardening-adr]]'
  - '[[2026-06-04-cross-campaign-hardening-research]]'
---


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
- [x] `P04.S16` - BIND-2: snapshot-build rejection of retired `source = "invoice"` bindings; `src/aeat/domain/calculations/registry`.

### Phase `P05` - HIGH: provenance + roundtrip coverage

Provenance on import; snapshot validation; and the persistence
roundtrip / anti-tautology gaps.

- [x] `P05.S17` - CALC-2: `import_external_filing` builds registry-sourced `CasillaObservation` rows; `src/aeat/application/filing`.
- [x] `P05.S18` - CALC-3: snapshot validator asserts every `input_kind="bound"` casilla has a binding definition; `src/aeat/domain/calculations/registry`.
- [x] `P05.S19` - PERS-4: no-op on verification - `SecureObjectRecord.object_key` and `SecureObjectWrite.object_key` are both already `str`; `the audit's `bytes`-vs-`str` premise was wrong. `test_secure_object_record_roundtrip_preserves_full_record_fields` already proves natural-key identity across the save→HMAC-column→load cycle; `src/aeat/adapters/persistence`.
- [x] `P05.S20` - PERS-5: `RecoveryRecord` serialization anti-tautology proof (5850e665e) - re-verified: no file-Envelope path exists; `added drop-field + mutate-field anti-tautology tests; 11 tests green; `src/aeat/adapters/persistence`.
- [x] `P05.S21` - PERS-6: `peek_metadata` consistency test + on-disk schema-version-drift anti-tautology (50cd0b7fe); `12 secure-objects tests green; `src/aeat/adapters/persistence`.
- [x] `P05.S22` - PERS-7: two-instance upsert-convergence test for `SecureObjectRepository` (45b383329) - two repos, one key, asserts single-row last-write-wins; `13 tests green; `src/aeat/adapters/persistence`.
- [x] `P05.S23` - EXIM-2: fichero-BOE RESERVED-field anti-tautology proof (ed4b529ac) - corrupt-the-literal test, 9 roundtrip tests green; `src/aeat/adapters/outbound/aeat/export/_formats`.
- [x] `P05.S24` - EXIM-3: asset-ledger delete-field anti-tautology proof (85ba9180b) - delete `cost_basis` from the encrypted JSON payload, assert ValidationError; `3 asset-roundtrip tests green; `src/aeat/adapters/persistence/profile`.

### Phase `P06` - HIGH: export coverage + Google Sheets guard

Lock export-adjacent coverage after the critical provenance path lands.

- [x] `P06.S25` - EXIM-4: document and test Google Sheets as a one-way export mirror (b37445ce2) - found and fixed a live defect: `_classify_metadata_match` never compared `registry_sha`, so a drifted-registry workbook classified `matches`; `added the gate, the one-way-mirror docstring contract, and the malformed-sheet pull probe; 33 google tests green; `src/aeat/adapters/outbound/google`.
- [x] `P06.S26` - EXIM-5: export tests for no-layout modelos, `binding_rows`, and computed fields (ec2085049) - added the two untested no-layout guard cases (modelo 303: `export_draft` raises `FilingExportError`, `verify_export` returns `MISSING`); `computed`-field shapes already exercised by the 130 layout round-trip, `binding`-field shapes by the 131 binding-derived test; 38 export tests green; `src/aeat/application/filing`.

### Phase `P07` - MED cluster

Close medium-severity calculation, persistence, CLI, boundary, export, and binding findings.

- [x] `P07.S27` - CALC-4/CALC-5/CALC-6 (4c486e840) - CALC-4 verified already-satisfied (the `_reject_non_decimal` defence-in-depth note already exists at `_formula_runtime.py:178-182`); `CALC-5 verified already-satisfied (per-source typed selector models + `_validated_*_selector` accessors + snapshot-time selector-shape gate already exist in `_bindings.py`/`_validate_references.py`); CALC-6 grounded the modelo-130 sign-propagation test with a docstring framing it as the rule-permitted structural assertion; `src/aeat/domain/calculations/registry`.
- [x] `P07.S28` - PERS-8/PERS-9 (7110dbf26) - PERS-8: on-disk `manifest.toml` datetime wire-format inspection test (bare RFC-3339 offset datetimes, `tomllib`-parseable to the exact aware datetime); `PERS-9: `EncryptionMetadata.associated_data_b64` made required so an absent AAD member is rejected at validation, distinguishing it from an explicit empty AAD; 10 manifest-io + 28 envelope tests green; `src/aeat/adapters/persistence`.
- [x] `P07.S29` - WCLI-5/WCLI-6 (86364440c) - WCLI-5: `_parse_bucket_event_types` now catches the failing token and raises a localized `cli.config.bucket.history.invalid_event_type` refusal (4 locales) naming the bad value + valid set, replacing the raw `str(exc)`; `WCLI-6: `_ledger.py` invoice-link handler routes through `resolve_error_message(exc)` instead of `str(exc)`, consistent with the apoderado/modelo/app-live error-rendering fixes; locale audit green; `src/aeat/entrypoints/cli`.
- [x] `P07.S30` - XDOM-7/XDOM-8/XDOM-9: all three verified already-satisfied - XDOM-7: `LedgerTransactionPayload` pydantic model exists (`ledger/_models.py:419`) and `LedgerReviewRow.transaction` already uses it, not `dict[str, object]`; `XDOM-8: `diagnostics.py` imports the public `validate_site_health_url` helper from the `browser` package surface, not the private `_URL_ADAPTER`; XDOM-9: `_iva_wallet_reconciliation.py` imports `IvaCompensationWalletObservation` from the public `sede` surface (exported in `sede/__init__.py`); `src/aeat/application src/aeat/adapters/outbound/aeat/sede`.
- [x] `P07.S31` - EXIM-6: verify verdict reports reserved-field unchecked casillas (0f412f364) - `DeclaracionVerifyResult.unchecked_casillas` was declared but `verify_export` never populated it; `now computes `draft casillas − parser-checked set` and reports it, with a coverage-partition test (modelo-130 `saldo-negativo-fin-periodo` surfaces as unchecked); 39 export tests green; `src/aeat/application/filing`.
- [x] `P07.S32` - BIND-3/BIND-4/BIND-5 - BIND-3 (e20cf8e34): numeric profile-binding Decimal-channel test (real snapshot extended with a controlled decimal `source="profile"` binding, asserts resolution into `binding_values` not the enum channel); `BIND-4 (dd53cef44): removed the four dead source kinds (`ledger`, `rental`, `vat`, `category`) from `DataBindingDefinition.source` after verifying zero TOML + code usage; BIND-5: dispositioned to `P09.S42` (GEN-6 / coordinator task #521) — the estimacion-directa profile-auto-resolution decision is the same item and is resolved there, not duplicated here; `src/aeat/domain/calculations/registry`.

### Phase `P08` - LOW cluster

Close lower-severity typing, persistence, boundary, and binding-stability findings.

- [x] `P08.S33` - CALC-7: tighten `ModeloInputsProviderProtocol.load_inputs` return type; `src/aeat/application/modelo`.
- [x] `P08.S34` - PERS-10/PERS-11: KDF-param witnesses and `SecureObjectNamespaceIntegrity` test; `src/aeat/adapters/persistence`.
- [x] `P08.S35` - XDOM-11/XDOM-12: re-point registry private imports, export `RegistrySnapshotRef`, and add non-303 period-binding tests; `src/aeat/domain/calculations/registry src/aeat/application/modelo`.
- [x] `P08.S36` - BIND-8/BIND-9: stabilise the `test_invoice_bindings` fixture filter and atribucion/refund source-kind disposition; `src/aeat/domain/calculations/registry`.

### Phase `P09` - carried-over coordinator items (Axis G)

Pre-existing coordinator task-list items folded into this rollout.

- [x] `P09.S37` - GEN-1 task 501: wire the live G313 Playwright driver actual fetch path; `src/aeat/adapters/outbound/aeat`.
- [x] `P09.S38` - GEN-2 task 506: triage the discovery-swarm legacy/shim inventory into fixes; `.vault/audit src/aeat`.
- [x] `P09.S39` - GEN-3 task 517: non-303 period-token test coverage for `_resolve_declaration_period_inputs`; `src/aeat/application/modelo`.
- [x] `P09.S40` - GEN-4 task 518: profile UUID-vs-label delegated to the `cli-workflow-redesign` campaign; `.vault/plan`.
- [x] `P09.S41` - GEN-5 task 520: CLI UX polish cluster cross-check against the `cli-workflow-redesign` bug-inventory clusters D/E; `.vault/audit src/aeat/entrypoints/cli`.
- [x] `P09.S42` - GEN-6 task 521: estimacion-directa profile auto-resolution disposition; `src/aeat/domain/calculations/registry`.

### Phase `P10` - verification + persona-testimonial re-audit

Run final gates and re-audit the operator-facing scenarios after all finding rows close.

- [x] `P10.S43` - run the full gate set: locale parity, CLI suite, registry suite, and touched-domain suites; `src/aeat`.
- [x] `P10.S44` - persona-testimonial pass over the hardened CLI and backend; `.vault/audit src/aeat`.
- [x] `P10.S45` - fold any testimonial regressions into a follow-up wave and re-run affected gates; `.vault/plan src/aeat`.
