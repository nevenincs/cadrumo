---
tags:
  - '#reference'
  - '#taxpayer-bank-accounts'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:0f7ab887b2e0c4248bffdb4287d1cd81ebacae5a1d87e3a3d8e85ef8dcc4a11a'
related:
  - "[[2026-10-04-taxpayer-bank-accounts-research]]"
  - "[[2026-10-04-modelo-360-solicitud-custody-reference]]"
---

# `taxpayer-bank-accounts` reference: `Own bank account sources, consumers and the 303 refusal map`

Code map, pinned at commit `20be1aef1e` on `feature/tui` (2026-10-04), of every place the taxpayer's own bank account is modelled, written, read or refused, of the ledger import and aggregation path those accounts must join, and of every current Modelo 303 refusal. Built from four bounded traces plus spot reads of the cited lines; discovery ran without semantic search (targeted grep and reads). Paths below are under `src/cadrumo/` unless stated.

## Summary

### Where own IBANs live today: nowhere that a production path writes

The account types exist, are validated and are consumed, but no production code constructs them with data.

- Types: `RefundAccount` (`domain/deadlines/models.py:165`, IBAN mod-97 check at 213-226, plus SWIFT-BIC, bank block and `sepa_marca`; no holder field) and `ChargeAccount` (`domain/deadlines/models.py:229`, IBAN only). They hang off `ModeloIVAProfile.refund_account` / `.charge_account` (`domain/deadlines/models.py:385-386`), default `None`.
- The only production constructor of `ModeloIVAProfile`, `_resolve_modelo_iva_profile` (`domain/deadlines/profiles.py:685`, body 701-723), never passes either field. Only tests populate them (`domain/deadlines/tests/test_account_iban_redaction.py`, `application/filing/tests/export_support.py`).
- The user profile schema (`_data/registry/cadrumo/user_profile/schema.toml`) declares no IBAN, BIC, bank or account field; the former `filing_export.iban`, `.charge_iban`, `.swift_bic` and `bank_*` paths were retired and are asserted absent by `application/user_profile/tests/test_retired_filing_export_paths.py`.
- Stale prose still points at the retired home: the `RefundAccount` docstring (`domain/deadlines/models.py:176-181`) says it lives on the profile schema, and `ModeloRefundAccountMissingError` (`application/modelo/action_errors.py:462`) tells the operator to configure an account on the profile.
- The Modelo 360 register is the only store that can hold an account: `Modelo360SolicitudEntry.refund_account` (`application/filing/producer_snapshot_m360.py:330`) with holder facts `Modelo360CuentaTitularFacts` (269-281), persisted by `Modelo360SolicitudRepository` (`adapters/persistence/profile/modelo_360_solicitud.py:28`, `load` 45, `declare` 49) under `PROFILE_MODELO_360_SOLICITUD_NAMESPACE` (`adapters/persistence/storage/secure_object_namespaces.py:368`). `declare` has no production caller; there is no operator write path. Reader: `application/modelo/export.py:981`, wired at `entrypoints/adapter_composition.py:476`.

### Dead, duplicated and incidental account data

| Item | Locator | State |
|---|---|---|
| `--charge-iban` wizard option | `application/wizard/commands.py:186-189`, locale text `locales/*/wizard.yml` | orphaned: no `WizardQuestion` uses it (`application/wizard/catalogue.py`) |
| `RefundAccount.sepa_marca` | `domain/deadlines/models.py` field | dead: the renderer derives the mark (`application/filing/record_field_renderer.py:394-404`, `domain/iva/sepa_marca.py:134`) and never reads the field |
| 210 account fact sets `irnr.ingreso.cuenta.*`, `irnr.devolucion.cuenta.*` | `core/filing_producer_key.py:374-394`; `application/filing/producer_snapshot.py:616-663`; `application/filing/export_producer.py:913` | dead (`Modelo210ProfileFacts` never built) and a second copy of `selected_account.*` |
| 200 `m200.numero_de_cuenta_iban*`, `m200.cuenta_bancaria_*` | `core/filing_producer_key.py:420-423, 491-492`; `application/filing/producer_snapshot_m200.py:297-300, 367-368` | dead (`Modelo200ProfileFacts` never built; 200 export refused at `producer_snapshot.py:1127`) and duplicated |
| Calculation casillas of `data_type="iban"` (100, 136, 220, 308, 309) | `application/modelo/calculate_input.py:787-816` | live but unrelated: casilla values, not the filing account |
| 720 identifiers `M720IdentifierScheme.IBAN` | `domain/foreign_assets/register.py:72-79, 117-121, 134-159`; `adapters/persistence/profile/foreign_assets.py:81, 85` | separate meaning (foreign asset identity); no production writer |
| OFX `ACCTID` | `adapters/inbound/financial/providers/ofx.py:152-157` (defaults to literal `"account"`), stored per row as `raw_fields["ACCTID"]` (264) | incidental, untyped, encrypted inside the transaction payload; never read back |
| AEAT live captures | `domain/portals/_entries/portal_domiciliacion_bancaria.py` | navigation link only; no capture of a domiciliación or refund account |

### Export consumption path and producer keys

- `application/modelo/export.py:_resolve_export_model_profile` (994-1021) builds only the 360, 303, 202, 111 and general profiles.
- Account selection (814-838): 360 takes the solicitud's account (818); every other modelo reads `workflow_profile.iva.refund_account` (821) and `.charge_account` (837), so a 111/130/131 domiciliación would read an IVA-profile field.
- `_require_export_accounts` (889-925): U without a charge account raises `ModeloChargeAccountMissingError` (910); a refund disposition or 303 Nota 3 (867-881) without a refund account raises `ModeloRefundAccountMissingError` (921). The "missing" test (884-886) accepts a SWIFT-only account, but the snapshot requires `iban` (`application/filing/producer_snapshot.py:1332-1345`), so a SWIFT-only account passes the refusal and fails later as `FAIL_MODELO_EXPORT`.
- Snapshot: `RefundAccountSelection` / `ChargeAccountSelection` (`producer_snapshot.py:1007-1025`), selected at 1325-1346; accounts stripped from the model profile (1349-1359, checked 1243-1246); disposition/account agreement validated at 1204-1219; 360 requires IBAN and BIC at 1142-1155 and raises plain `ValueError`, surfaced as `FAIL_MODELO_EXPORT` via `export.py:848-864`.
- Producer keys (`core/filing_producer_key.py`): `filing.result_disposition` (19); `selected_account.iban`, `.swift_bic`, `.bank_name`, `.bank_address`, `.bank_city`, `.bank_country_code` (60-65), filled by `selected_account_lexicals` (`export_producer.py:1305-1320`, used 1189-1194); `prior_domiciliation.action` (66); `m360.cuenta.titular_nombre`, `.titular_en_calidad_de`, `.divisa` (96-98, filled at `export_producer.py:720-722`).
- Registry consumers of `selected_account.*`: 111, 115, 117, 122, 123, 126, 128, 130, 131, 202, 216, 222, 303, 341, 353, 360, 714. 303 uses record `0010-record-m303-domiciliacion.toml` fields f005-f010 plus computed `sepa_marca` f011 (`_data/registry/aeat/modelos/303/revisions/2026-y-siguientes/export/0010-record-m303-domiciliacion.toml:5-172`). 360 uses `selected_account.iban`/`.swift_bic` and the `m360.cuenta.*` keys (`_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/export/0002-record-m360-solicitud.toml:228-284`) and declares no `filing.result_disposition`.

### Disposition and election resolution

- Vocabulary: `ResultDisposition` (`core/result_disposition.py:63`: C, D, G, I, N, V, U, X, B, R), `PaymentElection` (`core/payment_election.py:16`: INGRESO, DOMICILIACION, CUENTA_CORRIENTE), `RefundElection` (`core/refund_election.py:34`: COMPENSAR, DEVOLVER), `PriorDomiciliationElection`.
- Single resolver `resolve_modelo_result_disposition` (`application/modelo/result_disposition_resolution.py`): base from the spec's result casilla, `or DECLARATION_TYPE_FALLBACK` (INGRESO, defined at 88, applied at 196) for any modelo without a spec, which is how 360 records INGRESO in receipts and events. U is refused for any modelo but 303 by a modelo-name branch (261-265); CUENTA_CORRIENTE always refused (257); refund-election eligibility at 211, 231, 414; payment-election sign compatibility at 222.
- The domiciliación cutoff already exists as `payment_cutoff_on` on registry deadline windows (consumers `application/modelo/declarations_calendar.py:124`, `application/overview/calendar.py:298`, advisory context `application/modelo/work_plazo.py:352`); no export path gates U on it.

### Refusal codes on the account path

| Code | Raised at | Registered |
|---|---|---|
| `REFUSED_MODELO_CHARGE_ACCOUNT_MISSING` | `application/modelo/export.py:910` | `core/errors/registry/_domain_part2.py:331-336`; `locales/en/errors.yml:1140` |
| `REFUSED_MODELO_REFUND_ACCOUNT_MISSING` | `application/modelo/export.py:921` | `core/errors/registry/_domain_part2.py:321-326`; `locales/en/errors.yml:1163` |
| `INTEGRITY_FILING_PRODUCER_SNAPSHOT` (`m360_solicitud_undeclared`) | `application/modelo/export.py:986` | `core/errors/registry/_application_part3a1.py:217-219` |
| `FAIL_MODELO_EXPORT` for 360 without account/BIC | `application/filing/producer_snapshot.py:1153, 1155` via `export.py:861` | `core/errors/registry/_domain_part3.py:522-524` |
| `ERROR_FILING_EXPORT_VALIDATION` "SEPA marker requires a selected refund account" | `application/filing/record_field_renderer.py:394-404` | |

### Modelo 303 refusal inventory

Class A: caused by the missing account supplier or the account/election path, and fixed or reshaped by the account work. Class B: separate.

| # | Trigger | Locator | Class |
|---|---|---|---|
| 1 | No supplier for refund/charge account | `domain/deadlines/profiles.py:701-723` | A, root cause |
| 2 | `REFUSED_MODELO_CHARGE_ACCOUNT_MISSING` on every U | `application/modelo/export.py:907-913` | A |
| 3 | `REFUSED_MODELO_REFUND_ACCOUNT_MISSING` on every D/X and Nota 3 | `export.py:918-924`, `884-886`, `867-881` | A |
| 4 | Snapshot account refusal; SWIFT-only mismatch with #3 | `application/filing/producer_snapshot.py:1332-1345` | A |
| 5 | Snapshot disposition/account validators | `producer_snapshot.py:1204-1219` | A (stay as invariants) |
| 6 | SEPA marker without selected refund account | `record_field_renderer.py:394-404` | A |
| 7 | `REFUSED_MODELO_EXPORT_PRIOR_DOMICILIATION_ELECTION_REQUIRED` on every 303 export, rectificativa or not | `export.py:1537-1542` | A-adjacent: contradicts the KEEP neutral default of `2026-06-21-m303-carry-reconciliation-adr` |
| 8 | CANCEL_OR_MODIFY on revisions without `prior_domiciliation.action` (2022, 2023, 2024-hasta-08) | `export.py:621-647` | correct design gate, keep |
| 9 | Baseline-U proof chain for CANCEL_OR_MODIFY | `application/modelo/prior_domiciliation.py:49-235` | correct gate, keep |
| 10 | `REFUSED_MODELO_REFUND_ELECTION_NOT_ELIGIBLE` | `result_disposition_resolution.py:211, 231, 414` | correct gate, keep |
| 11 | `REFUSED_MODELO_PAYMENT_ELECTION_INCOMPATIBLE` | `result_disposition_resolution.py:222` | correct gate, keep |
| 12 | `REFUSED_MODELO_PAYMENT_ELECTION_CAPABILITY`: CUENTA_CORRIENTE always; U outside 303 | `result_disposition_resolution.py:257, 262` | A for U (modelo-name branch); G/V stays refused |
| 13 | No IVA profile for a C result | `result_disposition_resolution.py:393` | B |
| 14 | `REFUSED_MODELO_M303_RECTIFICATIVA_MOTIVE` | `application/modelo/amendment_actions.py:275` | B |
| 15 | `REFUSED_MODELO_M303_FILING_EVIDENCE`, incl. simplified-regime evidence branch unsupported | `application/modelo/m303_ordinary_filing_evidence_authoring.py:78-280`; `m303_filing_evidence.py:76-247` | B |
| 16 | `REFUSED_MODELO_M303_EXONERADO_390_ATTESTATION_UNADMISSIBLE` | `application/modelo/m303_exonerado_390_applicability_attestation.py:186` | B |
| 17 | `REFUSED_MODELO_EXPORT_EVIDENCE_MISSING` | `export.py:520-545, 1036-1039, 1380-1390` | B |
| 18 | 303 applicability errors | `application/filing/_m303_export_applicability.py:36-133` | B |
| 19 | `M303FilingFacts` validators (390 exemption, prorrata coverage, simplified result) | `producer_snapshot.py:911-937, 1183-1185` | B |
| 20 | `REFUSED_M303_CARRY_INGRESS` (about 35 sites) | `application/calculations/m303_carry_ingress.py:132-707` | B |
| 21 | Régimen simplificado calculation and annual handoff | `application/calculations/m303_regimen_simplificado.py:87-402` | B |
| 22 | Simplified-regime profile readiness | `application/modelo/m303_regimen_simplificado_scope.py:55-95` | B |
| 23 | Prorrata especial margin ungrounded, compensation, wallet reconciliation blocked | `domain/iva/prorrata_especial_parameters.py:109, 119`; `application/modelo/iva_wallet_gate.py:142` | B |
| 24 | `REFUSED_MODELO_EXPORT_UNSUPPORTED` | `export.py:600-618` | B, not triggered for current layouts |
| 25 | Envelope software identity is the development mock; export graded not presentable | `application/filing/export.py:236-246, 720-723`; `entrypoints/adapter_composition.py:490` | B, owned by the export-parity work |
| 26 | Autoconsumo del promotor base exports a [27] its printed boxes do not sum to | audit `2026-09-30-modelo-editor-workbench-audit` `m303-result-route` | B, open high |
| 27 | U past the domiciliación cutoff is not gated | absent at `export.py`; data at `payment_cutoff_on` | A, new gap |

The 303 registry's 29 producer keys all have runtime suppliers (`application/filing/export_producer.py:1167-1216`, foral overrides 1222-1248); the only unfillable fields are the `selected_account.*` ones. No 303 test is skipped or xfailed. Open 303-related plan steps owned elsewhere: `2026-10-03-live-verification-session-plan` S07, `2026-09-26-export-parity-plan` S11, `2026-10-02-registry-health-repair-plan` S29, `2026-10-02-duplication-remediation-plan` S05/S06/S08.

### Ledger import and aggregation path, and its defects

Surface: `app ledger` composes 18 command fragments (`entrypoints/cli/_app_ledger_command_specs.py:24`); register-style families with an add/list/update shape exist for counterparty, bienes-inversion and actividad-asset (`entrypoints/cli/_app_ledger_counterparty_command_specs.py`, `_app_ledger_bienes_inversion_command_specs.py`). The TUI ledger (`entrypoints/tui/ledger/`) writes through injected doors (`controller.py:357-497`). There is no ledger setup concept: no account, opening balance or saved provider configuration.

Import: `app ledger import --file --provider` (`entrypoints/cli/_app_ledger_operations_command_specs.py:252-329`) and `LedgerImportRequestV1` (`entrypoints/tui/ledger/models.py:206-218`) reach `application/ledger/import_operation.py:408, 465`, `actions_import.py:272-287`, provider selection `adapters/inbound/financial/ledger_import.py:80-89`, detection `providers/detection.py:58-79`, then `evaluate_import_rows` (`actions_import.py:168-269`) and the transaction catalogue co-commit. `RawProvenance` (`domain/transactions/raw_transaction.py:73-78`), `RawTransaction` (166-174) and `Transaction` carry no account identity. `derive_transaction_id` hashes amount, narrative, provider id and value date (`domain/transactions/models.py:113-121`); the import duplicate fingerprint hashes amount, currency, direction, normalised reference and value date (`domain/transactions/models.py:178-186`).

Aggregation to 303: `LedgerIvaAggregationSourceResolver` (`application/aggregation/modelo_bindings.py:331-405`) calls `aggregate_iva_ledger_observations_from_repositories` (`application/aggregation/iva_ledger.py:441`), which screens each transaction through `_iva_transaction.py` (period 154-172, EUR 175-194, direction 216-225, business class 226-240, required tax facts 280-288), then `resolve_iva_ledger_binding_values` (`iva_ledger.py:773`) maps onto the revision's 303 bindings. A transaction reaches 303 only after `ledger classify` sets base, rate and cuota (`entrypoints/cli/ledger_classify_fields.py:67`). Focused suites passed on 2026-10-04: `application/ledger/tests` 1499, `adapters/inbound/financial` 134, eleven IVA/303 aggregation files 153.

Defects found:

- D1 no own-account identity on any transaction (above).
- D2 cross-account false duplicates: the duplicate fingerprint omits the account, so the same amount and narrative on two own accounts on one day is skipped as a re-import (`application/ledger/actions_import.py:208-218`); a skipped business row never reaches 303.
- D3 no ledger setup surface.
- D4 linking an invoice copies no tax facts (`application/invoices/transaction_linking.py:44-79`); the invoice guard compares totals only (`application/aggregation/_modelo_bindings_invoice_iva_refusal.py:60-75`) and compares invoice-currency IVA with EUR ledger totals raw (the rule 07 finding).
- D5 TUI import preview/apply bind a path without a content digest (`entrypoints/tui/ledger/models.py:215-218`, `import_flow.py:265, 286`).
- D6 hash-then-reopen: `actions_import.py:279-282`; `providers/ofx.py:250-253`; `providers/detection.py:46` reads the whole file before a size guard.
- D7 provider tokens mislead: `--provider n26` runs auto-detection, `excel` maps to `XlsxProvider` though `XlsProvider` exists (`ledger_import.py:80, 86`); the TUI offers only auto, csv, ofx, xlsx, pdf-n26 (`entrypoints/tui/ledger/import_flow.py:37-43`).
- D8 `ledger import --period/--year` filter nothing and reuse export help text (`actions_import.py:364, 418`; `entrypoints/cli/_app_ledger_command_spec_support.py:375-380`).
- D9 TUI ledger review and evidence-row navigation pending (`entrypoints/tui/ledger/controller.py:755-772`).
- D10 detection logs a full source path on read failure (`providers/detection.py:48`).

### Analogues to reuse

- Encrypted singleton register with revision-guarded mutation: `adapters/persistence/profile/foreign_assets.py:41-89` on `adapters/persistence/profile/_secure_model_document.py`; 360 copies it.
- Namespace definition shape: `PROFILE_FOREIGN_ASSET_REGISTER_NAMESPACE` (`adapters/persistence/storage/secure_object_namespaces.py:353`), `FINANCIAL`, `BUCKET_LOCAL`, `STRUCTURED_CUSTODY`, key `default`.
- Ledger register CLI families: counterparty and bienes-inversion command specs above; registered operations under `application/ledger/`.
- IBAN validation and SEPA mark: `core/iban.py` (`IBAN_SHAPE_RE` 29, `normalise_iban` 43, `iban_mod_97` 63), `domain/iva/sepa_marca.py:134`.
- Domiciliación cutoff data: registry `payment_cutoff_on`.
