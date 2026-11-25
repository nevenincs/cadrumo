---
tags:
  - '#reference'
  - '#backend-served-surface'
date: '2026-11-03'
modified: '2026-11-03'
body_schema: 'body-v2'
body_hash: 'sha256:3ee14c79e5f9a05a58e8fc9c06b34e906e93418b3b503d5bebc95f533e718fb4'
related: []
---

# `backend-served-surface` reference: `Window-held words, facts and rules`

Where the desktop window and the Rust desktop host hold tax words, token-to-words maps, tax facts, eligibility rules and modelo-bound capabilities instead of rendering backend-served values. Read-only static inventory of this checkout on 2026-11-03. Each locator is a lead to verify against current code before a change.

## Summary

- The window holds more than 110 such sites across ledger (55), modelo workspace (22), modelo form (5), calendar (9), profile (7), AEAT sync (11) and shell (9) areas.
- Facts recur across areas: the reporting currency literal "EUR" and the annual period "0A" appear in ledger, modelo and Rust host code.
- Capabilities are hardwired to modelos: the evidence dialog to Modelo 303 and 390, the correction motive to Modelo 303, estimate groups to Modelo 130 and 100, the filing hand-off to Modelo 100 and 130.
- Served-word precedents already exist: `src/cadrumo/application/operations/error_detail.py:161` (`refusal_words`), `src/cadrumo/application/modelo/credit_resolution_contracts.py:146` (`answer_words`).
- Requests already carrying `output_language`: `src/cadrumo/application/ledger/bulk_classify_operation.py:84`, `src/cadrumo/application/modelo/credit_resolution_contracts.py:89`, `src/cadrumo/application/actividad_asset/activity_asset_contracts.py:384`.
- Existing `served` key families: `application.prorrata_register.served`, `application.modelo.credit_resolution.served` (`src/cadrumo/locales/*/application.yml`), `aggregation.retencion_soportada.served`, `aggregation.retencion_soportada_absence.served` (`src/cadrumo/locales/*/common.yml`).
- Relay contract checks: `native/desktop/CMakeLists.txt:345-348` runs `native/desktop/src-tauri/src/shell/ledger/relay_contracts.py --check` and `native/desktop/src-tauri/src/shell/modelo/relay_contracts.py --check`.

## Inventory

Read-only inventory of `native/desktop/frontend/src` (excluding `src/dev/fixtures`, stories, generated contracts; `src/dev/` itself was not read) and `native/desktop/src-tauri/src/shell`. Leads to verify against current code before changing.

Already in flight on the backend side, so not listed: the ledger classification flags (`ledgerContract.ts:154-168`), the three credit-resolution fields, TUI refusal copies. The S53 withholding refusal/absence words and the S51 unknown-dependents words are being handled by the desktop.

Columns: window locator | decides (words/fact/flag/capability) | token set or rule | backend that would serve it.

### Ledger (55)

#### Maps (window picks a sentence per token)
- `components/ledger/movements/movementWords.ts:61,65,69` | words | direction, lifecycle, classification tokens -> `desktop.ledger.direction.*` etc. | served label per token on the transaction
- `movementWords.ts:96-105` | words | `classified_by` prefixes rule:/llm:/derived: | served classified-by kind and label
- `movementWords.ts:125` | words | status -> `desktop.ledger.status.*` | served status label
- `movementWords.ts:130,132` | words | readiness reasons -> `desktop.ledger.reason.*`, `reason_detail` (tax text) | readiness reasons with served words
- `movementWords.ts:24,26,43,45`, `InvoiceLines.tsx:37,287`, `NewInvoiceEditor.tsx:566` | words | iva_category, category, family, irpf_category ids | labels served with the vocabulary lists
- `movements/movementsModel.ts:288-337` | flag | `REASON_FIX` reason -> preset/column | fix target served per reason
- `movements/MovementsSection.tsx:383`, `MovementsToolbar.tsx:101,353` | words | review status | served review status label
- `transfer/transferWords.ts:34,51,54`, `MovementsToolbar.tsx:70` | words | import refusal, diagnostics, provider, import issue | served words on the import operations
- `documents/documentWords.ts:20-49` | words | reading field names (incl. iva_rate, retention_rate) | label per reading field
- `documentWords.ts:54-78` | words | origins, groundings | provenance labels
- `documentWords.ts:89-100` | words | confirmation-block reasons (contradicted_regime, undetermined_establishment, unmodelled_invoice_class) | served reason words
- `documentWords.ts:112,124,128`, `DocumentViewer.tsx:57`, `EvidenceRecords.tsx:216` | words (generic) | batch status, source, hold, viewer refusal, media kind | served labels
- `invoices/invoiceWords.ts:20,23,26,33`, `InvoicesSection.tsx:439` | words | invoice kind, class, payment | served labels
- `setup/setupWords.ts:60-78` | words | `TOKEN_WORDS` families: capital.disposal, capital.kind, counterparty.scope, counterparty.source, prorrata.letra, prorrata.provenance, prorrata.kind, prorrata.regime, ratios.kind | label on each register row
- `setup/AccountsPane.tsx:375,435,437,683,710,792` | words | account role, holding | served labels
- `CapitalGoodsPane.tsx:199`, `ProrrataPane.tsx:417`, `RulesSection.tsx:424`, `RuleDialog.tsx:289` | words | refusal reason/code | `refusal_words` on those operations
- `WithholdingPane.tsx:422` | words | withholding origin | served label
- `inspector/inspectorWords.ts:98-129` | words | ledger event types | served event label
- `inspectorWords.ts:65-84` | words | revision states verificado_completo/presentado/borrador | served state label
- `assets/assetsWords.ts:170,240`, `AssetForm.tsx:80` | words | ~35 asset families listed in the window | served options with labels
- `assetsWords.ts:330`, `assetFields.ts:84,172` | words | field paths, fact labels, shapes | `label_key` per field path
- `assets/stockVocabulary.ts:77-109` | words | label family -> `application.inventory.labels.*` | served labels
- `setup/HealthSection.tsx:333,351` | words | health count names | served labels
- `editing/editingModel.ts:241` | fact | direction aliases IN/OUT/TRANSFER | accepted aliases served

#### Facts and rules
- reporting currency "EUR": `assets/assetsWords.ts:21`, `assetFormValues.ts:79`, `handoffWords.ts:77`, `movements/movementsModel.ts:354,585,784,975`, `MovementCells.tsx:192,218`, `MovementsSection.tsx:255,565`, `editing/MovementEditing.tsx:541`, `inspector/DetailsSection.tsx:123,130` | fact | `reporting_currency` per profile
- annual period "0A": `PeriodSelector.tsx:132,218,253,254,334`, `ProrrataPane.tsx:644`, `RatiosPane.tsx:314`, `WithholdingPane.tsx:564` | fact | period list / annual token served
- `movementsModel.ts:280,283,354` | fact | TO_CLASSIFY_REASON, NO_RATE_REASON, `currency !== "EUR" && value_in_eur === null` | readiness counts keyed by served roles
- `movementsModel.ts:161-200` | fact | COLUMN_PRESETS iva/irpf column groups | column groups by tax area
- `inspector/inspectorModel.ts:161-185,338-345` | fact | TAX_SETS, skip personal, quarterMove | applicability, skip and period served per field
- `movements/ClassifyDialog.tsx:91-115`, `MovementsSection.tsx:1027,1079` | rule | asksCategory, mixed needs share | classify-requirements read (overlaps the in-flight classification flags; check)
- `invoices/invoiceModel.ts:403,429`, `NewInvoiceEditor.tsx:541` | rule | issued + lease -> business_premises_lease fields | applicable sections served by preview
- `invoiceModel.ts:171`, `InvoiceLines.tsx:98,414` | rule | spending_category only on received | served field applicability
- `invoiceModel.ts:620-640` | rule | number suggestion for issued per class/year | number-suggestion operation
- `inspector/ClassifySection.tsx:505-509,608,624` | fact | M210 six fields, takesM210Income(direction), /^\d{2}$/ | m210 field list and validation served
- `setup/AccountsPane.tsx:59` | fact | MODELO /^\d{3}$/, hint "e.g. 303" | validation served
- `setup/WithholdingPane.tsx:52-66` | fact | certificate amount field list, default "0" | amount fields served
- `setup/ProrrataPane.tsx:253` | rule | elect_especial -> especial | regime per action served
- `assets/stockFieldDefinitions.ts:84-135,183`, `stockVocabulary.ts:137` | fact | purchase fields, PROOF_SLOTS iva_check | field set per movement kind
- `assets/assetFields.ts:436` | rule | absence free_election shows free_amount | field applicability
- `assets/assetWrites.ts:154-163`, `FilingHandoffPanel.tsx:68-72,122-175`, `handoffWords.ts:18-39,85-96` | fact | Modelo 100 / 130 coupling fields | generic handoff list keyed by served modelo

#### Wording with tax meaning (chosen by the window)
- `assets/assetFields.ts:435,437,545,623,753,797,801,804,810,860`
- `assets/assetsWords.ts:55,56,67,78-80,85,98,134`
- `assets/handoffWords.ts:19-22,29-39`, `FilingHandoffPanel.tsx:234,238`
- `assets/StockBookDetails.tsx:156-185`, `stockFieldDefinitions.ts:77-127,192,224`, `StockMovementForms.tsx:216`
- `documents/DraftReview.tsx:378,904,916`
- `editing/ReviewBlockers.tsx:402`, `ReviewDialog.tsx:126`, `CellEditor.tsx:373,381`
- `inspector/ClassifySection.tsx:360,404,651,655,727,867`, `ModelSuggestion.tsx:296`
- `invoices/InvoiceClassificationFields.tsx:22,50`, `InvoiceLines.tsx:126,127,420,421`, `InvoiceTotals.tsx:43-167`, `NewInvoiceEditor.tsx:231,477,494`, `StoredInvoiceEditor.tsx:112,258`
- `matching/matchingWords.ts:75`
- `setup/AccountsPane.tsx:377,378,501,796,799`
- `setup/CapitalGoodsPane.tsx:230,237,287,297,407,422,499`
- `setup/CounterpartiesPane.tsx:257,289,357,396,531`
- `setup/ProrrataPane.tsx:87,540,561,661,687-712,867-905`
- `setup/RatiosPane.tsx:193,364`
- `setup/WithholdingPane.tsx:105,561,576,749` (amount labels; refusal/absence words are S53)

### Modelo workspace (22)
- `components/modelo/workspace/Workspace.tsx:288` | words | next action -> `workspace.modelo.next_button.*` | served next-action words
- `workspace/CheckView.tsx:141` | words | level -> `workspace.modelo.level.*` | `entry.words` (already served for AttentionMark)
- `CheckView.tsx:60`, `SourcesView.tsx:147`, `CreditsView.tsx:184` | words | surface -> `surface.open.*` | served surface label
- `workspace/SourcesView.tsx:171` | words | reading state | served label
- `workspace/IvaWallet.tsx:153`, `IvaWalletDialog.tsx:79-92,199,205,354` | words | wallet key/mode/help, receipt kind switch | served words per action and receipt
- `dialogs/FilingView.tsx:328,791,809,516` | words | filter format, copy kinds, `origin.calculated` | served labels
- `dialogs/ReconciliationResult.tsx:55,59,86` | words | diff kind, field name | served labels
- `declarations/declarationsWords.ts:17` | words | AEAT state | served label
- `workspace/TaxationComparison.tsx:127,135` | fact | recommendation === "conjunta", conjunta_cuota_resultante | served recommendation words/flags
- `workspace/calculationEvidence.ts:65-124`, `CalculationEvidenceDialog.tsx:17-23`, `WorkspaceScreen.tsx:790` | capability | dialog hardwired to Modelo 303/390 attestation | generic evidence-question list on the form
- `workspace/CorrectionDialog.tsx:28,42,101,207`, `WorkspaceScreen.tsx:374` | fact | 303-specific rectificativa motive type/field | generic correction question
- `workspace/estimateRead.ts:179-196` | fact | m130_accumulated, m100_projection groups | generic estimate groups
- "EUR": `estimateRead.ts:145`, `TaxationComparison.tsx:35`, `IvaWallet.tsx:63`, `IvaWalletDialog.tsx:227,282,289` | fact | served currency
- `dialogs/FilingView.tsx:203,211` | fact (low) | artefact === "fichero_boe" | served artefact kind
- wording: `CalculationEvidenceDialog.tsx:52,75,86`; `TaxationComparison.tsx:126,134,244,253`; `EstimateView.tsx:108,112,235,248`; `IvaWallet.tsx:36,85,89,142,146`, `IvaWalletDialog.tsx:165`; `CreditsView.tsx:159,160`; `BorradorComparison.tsx:348`; `FilingView.tsx:614,863` and `filing.copy.*.detail`; `ImputationElection.tsx:229`

### Modelo form (5)
- `form/FieldRow.tsx:35`, `workspace/BoxLabel.tsx:15` | words | disclosure -> `workspace.modelo.disclosure.*`
- `FieldRow.tsx:179`, `form/ValueCell.tsx:242`, `details/Details.tsx:275` | words | surface correct/open
- `form/BoxNoteList.tsx:48,89` | words | note level
- `details/TodoRail.tsx:95` | words | origin
- `form/FormView.tsx:412` | fact | translated = language !== "es" | served `translated` flag

### Calendar (9)
- `components/calendar/CalendarEntryRow.tsx:54,55` | words | local filing state, AEAT submission state
- `calendar/calendarMarks.ts:45`, `components/FilingCalendar.tsx:842` | words | user_state
- `FilingCalendar.tsx:769,866` | words | event_type
- `FilingCalendar.tsx:795-802` | words | coverage advice reasons
- `shell/calendarEntries.ts:18` | fact | status === "UNKNOWN" | served close_known flag
- `shell/calendarEntries.ts:4` | fact | STATE_ORDER | served sort rank
- `shell/calendar.ts:27-33` | fact | default range -3/+9 months | served default window
- `shell/calendar.ts:106-123` | fact (low) | FAR_DAYS 60, MONTH_DAYS | distance wording
- `CalendarEntryRow.tsx:62` | words | payment_cutoff "Direct debit until {date}" | served label

### Profile (7)
- `shell/profileCenso.ts:53-70`, used at `ProfileSync.tsx:119`, `AeatAccessEditor.tsx:323,548` | words | requirement tokens -> `auth.sync.requirement.*` | served requirement words
- `components/profile/householdModel.ts:17` | fact | REPLACEMENT descendiente/ascendiente | replacement operation served per group
- `components/profile/AeatAccessEditor.tsx:45-49,167-178` | fact | DNI/NIE facts, default route, facts per provider | readiness requirement list
- `ProfileSync.tsx:126`, `shell/profileInput.ts:19`, `shell/profileRows.ts:176` | fact (low) | field paths identity.tax_id, auth.provider, auth.clave_movil_route
- wording: `AeatAccessEditor.tsx:448`; `ProfileSync.tsx:146`; `Household.tsx:563`

### AEAT sync (11)
- `components/aeatSync/AeatSyncPage.tsx:368`, `AeatSyncProgress.tsx:130`, `Results.tsx:225` | words | area name/about
- `AeatSyncPage.tsx:42-47` | words | COUNT_KEYS
- `FiledResults.tsx:33,54,114` | words | record status, difference, match group
- `BorradorImport.tsx:113`, `NotificationResults.tsx:97` | words
- `Results.tsx:34-41` | words | area-dependent new/changed keys
- `AeatSyncPage.tsx:79`, `AeatSyncProgress.tsx:96-144` | words (generic) | attempt outcome, progress, reasons
- `shell/aeatSync.ts:5-16` | fact | area id list and order | served area list
- `shell/aeatSync.ts:61`, `AeatSyncPage.tsx:159` | fact | borrador is file-only | served capability per area
- wording: area name/about; `NotificationResults.tsx:72` (legal statement about receipt); `FiledResults.tsx:16,21` (low)

### Shell (9)
- `shell/ledgerGrammar.ts:391-488` | fact | periodOf, stepPeriod, parsePeriodCode, periodSpan | served period of a date, step and span
- `shell/ledgerCommands.ts:207-270` | rule | classify: mixed needs share, non-personal needs category, usage_ratio_id | served classify plan
- `shell/ledgerPlan.ts:588-593`, `shell/ledgerImports.ts:23-29`, `components/ledger/useLedgerPage.ts:87`, `ImportDialog.tsx:1207` | fact | quarter bucketing, default period = current quarter
- `shell/ledgerCommands.ts:21`, `SelectionInspector.tsx:96` | words | CLASSIFICATION_OF duplicated constant
- Rust `src-tauri/src/shell/aeat_sync/mod.rs:47,1239` | fact | BORRADOR_PERIOD = "0A"
- Rust `aeat_sync/admitted.rs:30-66`, `mod.rs:481-491` | fact | area order, per-area definitions, iva_wallet -> vat | served area catalogue
- Rust `aeat_sync/outcome.rs:11-45` | words | NO_ACCESS REFUSED_* codes -> reason token
- Rust `user_profile.rs:37-39,776-801` | fact | AUTH_FACT_PATHS, Descendants/Ascendants/ImputationElection variants
- Rust `modelo/admitted.rs:77-85,112-117,179,186` | fact (low) | allow-list entries named per modelo (protocol names)
