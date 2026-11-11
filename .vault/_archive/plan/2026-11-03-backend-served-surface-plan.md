---
tags:
  - '#plan'
  - '#backend-served-surface'
date: '2026-11-03'
tier: L2
related:
  - '[[2026-11-03-backend-served-surface-adr]]'
  - '[[2026-11-02-operation-refusal-words-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
modified: '2026-11-04'
body_schema: body-v2
body_hash: 'sha256:6ef34df8b61054e37332572797527d99a657a80f01c7faabc837b52eed7359fd'
---

# `backend-served-surface` plan

Make every registered operation serve its own words, tax facts, eligibility flags and capabilities, so the CLI, TUI and desktop render them only.

## Description

Approved 2026-11-03. Authorization basis: the operator's direct rulings of 2026-11-03, restated several times: "the frontend represents the backend's data and the frontend should never be allowed to hardcode tax facts or wording. that is what the backend is for."; "please build out all backend capability so that the frontend requires no frontend. Why? because cli tui and frontend should derive from the backend."; "ensure backend registers all required operations and data, frontend shouldn't need to hardcode tax details".

The campaign moves every tax word, token-to-words map, tax fact, eligibility rule and modelo-bound capability held by the desktop window, the Rust desktop host and the TUI into the owning backend operation. Each Step serves one backend family, then deletes the paired window copy under the deletion protocol of `2026-11-03-backend-served-surface-adr`. A backend session serves each family; the desktop frontend session deletes its window copy as each lands. The Step list comes from the inventory in `2026-11-03-backend-served-surface-reference`; its locators are leads to verify against current code before each change.

Decision coverage. `2026-11-03-backend-served-surface-adr` (accepted) governs every Phase: the field naming (`<thing>_words` with `<thing>_words_language`), the `served` key families, the request `output_language`, surface neutrality, the glyph and generic-chrome exceptions and the deletion protocol. `2026-11-02-operation-refusal-words-adr` (accepted) governs every Step that serves refusal words, chiefly P06.S40 and P09.S51. The 2026-10-27 and 2026-11-03 amendments of `2026-10-04-desktop-shell-adr` govern the window deletions in every Phase. No other costly decision is involved.

In-flight Steps carried into this plan: P01.S03 (ledger classification flags), P03.S17 (credit-resolution door fields), P06.S31 (ledger staged-check blockers), P06.S32 (activity-asset hand-off, left-out and finding words) and P09.S51 (TUI register refusal copies). Step P01.S54 of `2026-11-02-desktop-renta-plan` names the same deletion campaign and is carried out by this plan's Steps; the withholding words of that plan's P01.S53 and the unknown-dependents words of its P01.S51 stay with that plan.

Phase order: P01 shell period arithmetic and the classify plan; P02 ledger facts and rules; P03 modelo workspace facts; P04 calendar and AEAT sync catalogues, with the Rust relay facts; P05 profile; P06 to P09 word maps by area; P10 the protective check.

## Steps

### Phase `P01` - shell period arithmetic and the classify plan

The backend serves ledger period arithmetic and the classify plan, and the window deletes its period grammar and classify rules.

- [x] `P01.S01` - Serve the period of a date, the next and previous period and a period's span on the ledger reads from the canonical period owner; then delete periodOf, stepPeriod, parsePeriodCode and periodSpan from the window; `src/cadrumo/core/period.py, src/cadrumo/application/ledger/readiness_query.py, native/desktop/frontend/src/shell/ledgerGrammar.ts`.
- [x] `P01.S02` - Serve the ledger's default period and quarter bucketing on the ledger and import reads; then delete the window's current-quarter default and quarter bucketing; `src/cadrumo/application/ledger/import_operation.py, native/desktop/frontend/src/shell/ledgerPlan.ts, native/desktop/frontend/src/shell/ledgerImports.ts, native/desktop/frontend/src/components/ledger/useLedgerPage.ts, native/desktop/frontend/src/components/ledger/transfer/ImportDialog.tsx`.
- [x] `P01.S03` - Finish the in-flight ledger classification flags (which classification asks for a category, which needs a mixed-use share) on the entry options read; then delete the window's flag table and the ClassifyDialog rules; `src/cadrumo/application/ledger/entry_options_operation.py, native/desktop/frontend/src/shell/ledgerContract.ts, native/desktop/frontend/src/components/ledger/movements/ClassifyDialog.tsx`.
- [ ] `P01.S04` - Serve the classify plan (share, category and usage ratio each classification needs) from the classification preflight; then delete the window's classify command builder and its duplicated CLASSIFICATION_OF constant; `src/cadrumo/application/ledger/preflight_operation.py, native/desktop/frontend/src/shell/ledgerCommands.ts, native/desktop/frontend/src/components/ledger/inspector/SelectionInspector.tsx`.

### Phase `P02` - ledger facts and rules

The ledger reads serve the reporting currency, the annual period, readiness roles, column groups, Modelo 210 fields, invoice applicability and the filing hand-off, and the window deletes its copies.

- [ ] `P02.S05` - Serve reporting_currency per profile on the ledger, invoice and asset reads; then delete every window EUR literal in the ledger components; `src/cadrumo/application/ledger/read_ports.py, native/desktop/frontend/src/components/ledger/movements/movementsModel.ts, native/desktop/frontend/src/components/ledger/assets/assetsWords.ts`.
- [ ] `P02.S06` - Serve the period list and the annual period token for ledger and register period selectors; then delete the window's 0A literals; `src/cadrumo/core/period.py, native/desktop/frontend/src/components/ledger/PeriodSelector.tsx, native/desktop/frontend/src/components/ledger/setup/ProrrataPane.tsx, native/desktop/frontend/src/components/ledger/setup/RatiosPane.tsx, native/desktop/frontend/src/components/ledger/setup/WithholdingPane.tsx`.
- [ ] `P02.S07` - Serve readiness counts keyed by served roles (to classify, no rate, foreign currency without a EUR value) and the fix target per reason; then delete TO_CLASSIFY_REASON, NO_RATE_REASON and REASON_FIX; `src/cadrumo/application/ledger/readiness_query.py, src/cadrumo/application/ledger/readiness_routes.py, native/desktop/frontend/src/components/ledger/movements/movementsModel.ts`.
- [ ] `P02.S08` - Serve ledger column groups by tax area on the entry options read; then delete COLUMN_PRESETS; `src/cadrumo/application/ledger/entry_options_operation.py, native/desktop/frontend/src/components/ledger/movements/movementsModel.ts`.
- [ ] `P02.S09` - Serve inspector field applicability, the personal-use skip and each field's period on the entry options read; then delete TAX_SETS and quarterMove; `src/cadrumo/application/ledger/entry_options_operation.py, native/desktop/frontend/src/components/ledger/inspector/inspectorModel.ts`.
- [ ] `P02.S10` - Serve the Modelo 210 field list, its applicability by direction and its validation; then delete the window's six-field list, takesM210Income and its pattern; `src/cadrumo/application/aggregation/irnr_income_ledger.py, src/cadrumo/application/ledger/entry_options_operation.py, native/desktop/frontend/src/components/ledger/inspector/ClassifySection.tsx`.
- [ ] `P02.S11` - Serve invoice field applicability (lease fields for an issued lease, spending category for received invoices) on the invoice add preview; then delete the window's rules; `src/cadrumo/application/invoices/catalogue_add_contracts.py, native/desktop/frontend/src/components/ledger/invoices/invoiceModel.ts, native/desktop/frontend/src/components/ledger/invoices/InvoiceLines.tsx, native/desktop/frontend/src/components/ledger/invoices/NewInvoiceEditor.tsx`.
- [ ] `P02.S12` - Add an issued-invoice number suggestion per class and year to the invoice catalogue; then delete the window's number suggestion; `src/cadrumo/application/invoices/catalogue_read_projection.py, native/desktop/frontend/src/components/ledger/invoices/invoiceModel.ts`.
- [ ] `P02.S13` - Serve setup register facts: the modelo identifier validation, withholding certificate amount fields and defaults, and the prorrata regime per action; then delete the window's patterns, field list and regime map; `src/cadrumo/application/prorrata_register/service.py, src/cadrumo/application/retencion_soportada_certificado/, native/desktop/frontend/src/components/ledger/setup/AccountsPane.tsx, native/desktop/frontend/src/components/ledger/setup/WithholdingPane.tsx, native/desktop/frontend/src/components/ledger/setup/ProrrataPane.tsx`.
- [ ] `P02.S14` - Serve stock movement field sets and proof slots per movement kind, and asset field applicability such as free-election amounts; then delete the window's field definitions; `src/cadrumo/application/inventory/, src/cadrumo/application/actividad_asset/activity_asset_read_models.py, native/desktop/frontend/src/components/ledger/assets/stockFieldDefinitions.ts, native/desktop/frontend/src/components/ledger/assets/stockVocabulary.ts, native/desktop/frontend/src/components/ledger/assets/assetFields.ts`.
- [ ] `P02.S15` - Serve a generic filing hand-off list keyed by served modelo in place of the Modelo 100 and 130 coupling; then delete the window's coupling fields; `src/cadrumo/application/actividad_asset/activity_asset_projections.py, native/desktop/frontend/src/components/ledger/assets/assetWrites.ts, native/desktop/frontend/src/components/ledger/assets/FilingHandoffPanel.tsx, native/desktop/frontend/src/components/ledger/assets/handoffWords.ts`.
- [ ] `P02.S16` - Serve the accepted direction aliases on the entry options read; then delete the window's IN, OUT and TRANSFER aliases; `src/cadrumo/application/ledger/entry_options_operation.py, native/desktop/frontend/src/components/ledger/editing/editingModel.ts`.

### Phase `P03` - modelo workspace facts

The modelo workspace reads serve the credit-resolution door, a generic evidence question, a generic correction question, estimate groups, the comparison recommendation and workspace facts, and the window deletes its per-modelo branches.

- [x] `P03.S17` - Finish the in-flight credit-resolution door fields (refusal sentence, the acceptance answer sentence, the finding id with the answer a check line offers); then delete the window's joins that decide accept or revoke; `src/cadrumo/application/modelo/credit_resolution_contracts.py, native/desktop/frontend/src/components/modelo/workspace/CreditsView.tsx`.
- [ ] `P03.S18` - Serve a generic evidence-question list on the work form in place of the 303 and 390 attestation dialog; then delete calculationEvidence.ts and the dialog's modelo branch; `src/cadrumo/application/modelo/m303_attestation_operation.py, src/cadrumo/application/modelo/work_form.py, native/desktop/frontend/src/components/modelo/workspace/calculationEvidence.ts, native/desktop/frontend/src/components/modelo/workspace/CalculationEvidenceDialog.tsx, native/desktop/frontend/src/components/modelo/workspace/WorkspaceScreen.tsx`.
- [ ] `P03.S19` - Serve a generic correction question with its motive field from the amendment context; then delete the window's 303 rectificativa motive; `src/cadrumo/application/modelo/amendment_context_operation.py, native/desktop/frontend/src/components/modelo/workspace/CorrectionDialog.tsx, native/desktop/frontend/src/components/modelo/workspace/WorkspaceScreen.tsx`.
- [ ] `P03.S20` - Serve generic estimate groups from the projection read; then delete the window's m130_accumulated and m100_projection groups; `src/cadrumo/application/modelo/projection_operation.py, native/desktop/frontend/src/components/modelo/workspace/estimateRead.ts`.
- [ ] `P03.S21` - Serve the taxation comparison recommendation as a flag and words; then delete the window's conjunta comparison; `src/cadrumo/application/modelo/taxation_comparison_operation.py, native/desktop/frontend/src/components/modelo/workspace/TaxationComparison.tsx`.
- [ ] `P03.S22` - Serve workspace facts: the currency on estimate, comparison and wallet reads, the export artefact kind and the form's translated flag; then delete the window's EUR literals, fichero_boe test and language test; `src/cadrumo/application/modelo/work_form.py, src/cadrumo/application/modelo/iva_wallet_balance_operation.py, src/cadrumo/application/modelo/export_operation.py, native/desktop/frontend/src/components/modelo/workspace/IvaWalletDialog.tsx, native/desktop/frontend/src/components/modelo/dialogs/FilingView.tsx, native/desktop/frontend/src/components/modelo/form/FormView.tsx`.

### Phase `P04` - calendar and AEAT sync catalogues

The calendar read and the AEAT sync status serve their facts and area catalogue, and the window and the Rust relay delete their copies.

- [ ] `P04.S23` - Serve calendar facts: a close_known flag, a sort rank per state, the default window and distance buckets; then delete STATE_ORDER, the UNKNOWN test, the default range and FAR_DAYS; `src/cadrumo/application/overview/read_calendar_projection.py, native/desktop/frontend/src/shell/calendarEntries.ts, native/desktop/frontend/src/shell/calendar.ts`.
- [ ] `P04.S24` - Serve the AEAT sync area catalogue (ids, order, per-area definitions, tax area per capture, file-only capability); then delete the window's area list and the Rust area definitions; `src/cadrumo/application/aeat_sync/status_operation.py, native/desktop/frontend/src/shell/aeatSync.ts, native/desktop/frontend/src/components/aeatSync/AeatSyncPage.tsx, native/desktop/src-tauri/src/shell/aeat_sync/admitted.rs, native/desktop/src-tauri/src/shell/aeat_sync/mod.rs`.
- [ ] `P04.S25` - Serve the Borrador capture period and the no-access reason per refusal code on the capture results; then delete the Rust BORRADOR_PERIOD and the REFUSED_* code map; `src/cadrumo/application/live/, native/desktop/src-tauri/src/shell/aeat_sync/mod.rs, native/desktop/src-tauri/src/shell/aeat_sync/outcome.rs`.
- [ ] `P04.S26` - Derive the modelo relay allow-list entries from the operation contract manifest; then delete the hand-named per-modelo entries; `native/desktop/src-tauri/src/shell/modelo/relay_contracts.py, native/desktop/src-tauri/src/shell/modelo/admitted.rs`.

### Phase `P05` - profile

The profile and authentication reads serve sync requirements, access facts per provider, household replacement and field paths, and the window and Rust host delete their copies.

- [ ] `P05.S27` - Serve sync requirement words on the sync readiness read; then delete the window's requirement-token map; `src/cadrumo/application/auth/sync_readiness.py, src/cadrumo/application/auth/sync_requirement_text.py, native/desktop/frontend/src/shell/profileCenso.ts`.
- [ ] `P05.S28` - Serve the readiness requirement list per provider (identity facts, default Cl@ve Movil route); then delete the window's per-provider facts and the Rust AUTH_FACT_PATHS; `src/cadrumo/application/auth/sync_readiness.py, src/cadrumo/application/auth/preferences.py, native/desktop/frontend/src/components/profile/AeatAccessEditor.tsx, native/desktop/src-tauri/src/shell/user_profile.rs`.
- [ ] `P05.S29` - Serve the replacement operation per household group; then delete the window's REPLACEMENT map and the Rust group variants; `src/cadrumo/application/user_profile/descendant_rows.py, src/cadrumo/application/user_profile/ascendant_rows.py, native/desktop/frontend/src/components/profile/householdModel.ts, native/desktop/src-tauri/src/shell/user_profile.rs`.
- [ ] `P05.S30` - Serve profile field paths and the access, sync and household sentences with tax meaning; then delete the window's field-path literals and wording; `src/cadrumo/application/user_profile/, native/desktop/frontend/src/components/profile/AeatAccessEditor.tsx, native/desktop/frontend/src/components/profile/ProfileSync.tsx, native/desktop/frontend/src/components/profile/Household.tsx, native/desktop/frontend/src/shell/profileInput.ts, native/desktop/frontend/src/shell/profileRows.ts`.

### Phase `P06` - ledger word maps

The ledger operations serve the words of their own records, and the window deletes its ledger token-to-words maps.

- [x] `P06.S31` - Finish the in-flight staged-check blocker words; then delete the window's blocker words; `src/cadrumo/application/ledger/staged_check.py, src/cadrumo/application/ledger/staged_check_contracts.py, native/desktop/frontend/src/components/ledger/editing/ReviewBlockers.tsx`.
- [ ] `P06.S32` - Finish the in-flight activity-asset hand-off, left-out and finding words; then delete the window's hand-off and finding words; `src/cadrumo/application/actividad_asset/activity_asset_results.py, native/desktop/frontend/src/components/ledger/assets/handoffWords.ts, native/desktop/frontend/src/components/ledger/assets/FilingHandoffPanel.tsx`.
- [ ] `P06.S33` - Serve transaction labels on each row: direction, lifecycle, classification, status, classified-by kind and review status; then delete movementWords.ts maps and the toolbar's review-status words; `src/cadrumo/application/ledger/lifecycle_projections.py, src/cadrumo/application/ledger/review_projection.py, native/desktop/frontend/src/components/ledger/movements/movementWords.ts, native/desktop/frontend/src/components/ledger/movements/MovementsToolbar.tsx, native/desktop/frontend/src/components/ledger/movements/MovementsSection.tsx`.
- [ ] `P06.S34` - Serve readiness reason words with their detail; then delete the window's reason words; `src/cadrumo/application/ledger/readiness_routes.py, native/desktop/frontend/src/components/ledger/movements/movementWords.ts`.
- [ ] `P06.S35` - Serve labels with the vocabulary lists for IVA category, category, family and IRPF category; then delete the window's vocabulary words; `src/cadrumo/application/ledger/entry_options_operation.py, native/desktop/frontend/src/components/ledger/movements/movementWords.ts, native/desktop/frontend/src/components/ledger/invoices/InvoiceLines.tsx, native/desktop/frontend/src/components/ledger/invoices/NewInvoiceEditor.tsx`.
- [ ] `P06.S36` - Serve import words: refusal, diagnostics, provider and import issue; then delete transferWords.ts maps; `src/cadrumo/application/ledger/import_operation.py, native/desktop/frontend/src/components/ledger/transfer/transferWords.ts, native/desktop/frontend/src/components/ledger/movements/MovementsToolbar.tsx`.
- [ ] `P06.S37` - Serve document evidence words: reading field names, origins, groundings, confirmation-block reasons, batch status, source, hold, viewer refusal and media kind; then delete documentWords.ts maps and the draft-review wording; `src/cadrumo/application/ledger/evidence_read_operation.py, src/cadrumo/application/ledger/grounded_reading.py, native/desktop/frontend/src/components/ledger/documents/documentWords.ts, native/desktop/frontend/src/components/ledger/documents/DraftReview.tsx, native/desktop/frontend/src/components/ledger/documents/DocumentViewer.tsx`.
- [ ] `P06.S38` - Serve invoice words: kind, class, payment, classification fields, line and totals sentences; then delete invoiceWords.ts and the editors' tax wording; `src/cadrumo/application/invoices/catalogue_read_projection.py, native/desktop/frontend/src/components/ledger/invoices/invoiceWords.ts, native/desktop/frontend/src/components/ledger/invoices/InvoiceTotals.tsx, native/desktop/frontend/src/components/ledger/invoices/InvoiceClassificationFields.tsx, native/desktop/frontend/src/components/ledger/invoices/StoredInvoiceEditor.tsx`.
- [ ] `P06.S39` - Serve register row labels for capital goods, counterparties, prorrata, ratios, accounts, withholding origin and health counts; then delete the TOKEN_WORDS families and the panes' label maps; `src/cadrumo/application/prorrata_register/service.py, src/cadrumo/application/bienes_inversion/registered_operation.py, native/desktop/frontend/src/components/ledger/setup/setupWords.ts, native/desktop/frontend/src/components/ledger/setup/AccountsPane.tsx, native/desktop/frontend/src/components/ledger/setup/HealthSection.tsx`.
- [ ] `P06.S40` - Serve refusal_words on the capital goods, prorrata and rule operations and the setup panes' tax sentences; then delete the panes' refusal and tax wording; `src/cadrumo/application/bienes_inversion/registered_operation.py, src/cadrumo/application/prorrata_register/service.py, native/desktop/frontend/src/components/ledger/setup/CapitalGoodsPane.tsx, native/desktop/frontend/src/components/ledger/setup/ProrrataPane.tsx, native/desktop/frontend/src/components/ledger/setup/CounterpartiesPane.tsx, native/desktop/frontend/src/components/ledger/setup/RatiosPane.tsx, native/desktop/frontend/src/components/ledger/setup/RulesSection.tsx`.
- [ ] `P06.S41` - Serve ledger event and revision-state labels and the classify section's tax sentences; then delete inspectorWords.ts maps and ClassifySection wording; `src/cadrumo/application/ledger/, native/desktop/frontend/src/components/ledger/inspector/inspectorWords.ts, native/desktop/frontend/src/components/ledger/inspector/ClassifySection.tsx, native/desktop/frontend/src/components/ledger/inspector/ModelSuggestion.tsx`.
- [ ] `P06.S42` - Serve asset families with labels, a label_key per asset field path and stock labels; then delete assetsWords.ts, assetFields.ts and stockVocabulary.ts wording; `src/cadrumo/application/actividad_asset/activity_asset_read_models.py, src/cadrumo/application/inventory/, native/desktop/frontend/src/components/ledger/assets/assetsWords.ts, native/desktop/frontend/src/components/ledger/assets/assetFields.ts, native/desktop/frontend/src/components/ledger/assets/stockVocabulary.ts, native/desktop/frontend/src/components/ledger/assets/StockBookDetails.tsx`.
- [ ] `P06.S43` - Serve the editing and matching sentences with tax meaning; then delete the review dialog, cell editor and matching wording; `src/cadrumo/application/ledger/, native/desktop/frontend/src/components/ledger/editing/ReviewDialog.tsx, native/desktop/frontend/src/components/ledger/editing/CellEditor.tsx, native/desktop/frontend/src/components/ledger/matching/matchingWords.ts`.

### Phase `P07` - modelo workspace and form word maps

The modelo workspace and form reads serve the words of their own records, and the window deletes its modelo token-to-words maps.

- [ ] `P07.S44` - Serve next-action, level, surface and reading-state words on the workspace read; then delete the window's next_button, level, surface.open and reading-state maps; `src/cadrumo/application/modelo/workspace.py, native/desktop/frontend/src/components/modelo/workspace/Workspace.tsx, native/desktop/frontend/src/components/modelo/workspace/CheckView.tsx, native/desktop/frontend/src/components/modelo/workspace/SourcesView.tsx, native/desktop/frontend/src/components/modelo/workspace/CreditsView.tsx`.
- [ ] `P07.S45` - Serve IVA wallet words per action and receipt kind; then delete the wallet's key, mode, help and receipt-kind maps; `src/cadrumo/application/modelo/iva_wallet_balance_operation.py, native/desktop/frontend/src/components/modelo/workspace/IvaWallet.tsx, native/desktop/frontend/src/components/modelo/workspace/IvaWalletDialog.tsx`.
- [ ] `P07.S46` - Serve filing view, reconciliation and declaration-state words (format filter, copy kinds and details, origin, difference kind, field name, AEAT state); then delete the window's maps; `src/cadrumo/application/modelo/export_operation.py, src/cadrumo/application/modelo/filing_chain_reconciliation.py, src/cadrumo/application/modelo/declarations_list_operation.py, native/desktop/frontend/src/components/modelo/dialogs/FilingView.tsx, native/desktop/frontend/src/components/modelo/dialogs/ReconciliationResult.tsx, native/desktop/frontend/src/components/modelo/declarations/declarationsWords.ts`.
- [ ] `P07.S47` - Serve the workspace companion sentences with tax meaning (evidence, comparison, estimate, credits, borrador comparison, imputation election) with their P03 reads; then delete the window's wording; `src/cadrumo/application/modelo/, native/desktop/frontend/src/components/modelo/workspace/EstimateView.tsx, native/desktop/frontend/src/components/modelo/workspace/BorradorComparison.tsx, native/desktop/frontend/src/components/modelo/workspace/ImputationElection.tsx`.
- [ ] `P07.S48` - Serve form words: disclosure, correct and open surfaces, note level and origin on the work form; then delete the form's maps; `src/cadrumo/application/modelo/work_form.py, native/desktop/frontend/src/components/modelo/form/FieldRow.tsx, native/desktop/frontend/src/components/modelo/workspace/BoxLabel.tsx, native/desktop/frontend/src/components/modelo/form/ValueCell.tsx, native/desktop/frontend/src/components/modelo/form/BoxNoteList.tsx, native/desktop/frontend/src/components/modelo/details/TodoRail.tsx, native/desktop/frontend/src/components/modelo/details/Details.tsx`.

### Phase `P08` - calendar and AEAT sync word maps

The calendar and AEAT sync reads serve the words of their own records, and the window deletes its calendar and sync token-to-words maps.

- [ ] `P08.S49` - Serve calendar words: local filing state, AEAT submission state, user state, event type, coverage advice reasons and the payment cut-off label; then delete the calendar maps; `src/cadrumo/application/overview/read_calendar_item_projection.py, src/cadrumo/application/overview/coverage.py, src/cadrumo/application/overview/calendar_events.py, native/desktop/frontend/src/components/calendar/CalendarEntryRow.tsx, native/desktop/frontend/src/components/calendar/calendarMarks.ts, native/desktop/frontend/src/components/FilingCalendar.tsx`.
- [ ] `P08.S50` - Serve AEAT sync words: area name and about, counts, record status, difference, match group, new and changed, attempt outcome, progress, reasons, Borrador import and notification results; then delete the sync pages' maps; `src/cadrumo/application/aeat_sync/status_operation.py, src/cadrumo/application/aeat_sync/reconciliation_reader.py, native/desktop/frontend/src/components/aeatSync/AeatSyncPage.tsx, native/desktop/frontend/src/components/aeatSync/AeatSyncProgress.tsx, native/desktop/frontend/src/components/aeatSync/Results.tsx, native/desktop/frontend/src/components/aeatSync/FiledResults.tsx, native/desktop/frontend/src/components/aeatSync/NotificationResults.tsx, native/desktop/frontend/src/components/aeatSync/BorradorImport.tsx`.

### Phase `P09` - TUI and CLI word maps

The TUI and CLI render served words only, and their own tax sentence copies are deleted.

- [ ] `P09.S51` - Finish the in-flight TUI register refusal copies (prorrata, capital goods, inventory, calendar setup-incomplete, evidence confirmation, IVA rate error, invoice defaults) by rendering the served refusal_words; then delete the TUI's own sentences; `src/cadrumo/entrypoints/tui/ledger/registers_prorrata.py, src/cadrumo/entrypoints/tui/ledger/registers_capital_goods.py, src/cadrumo/entrypoints/tui/ledger/registers_inventory.py, src/cadrumo/entrypoints/tui/declarations/calendar.py, src/cadrumo/entrypoints/tui/ledger/invoice_entry_wording.py`.
- [ ] `P09.S52` - Switch the remaining TUI token-to-words maps to the fields served in P06 to P08; then delete each map; `src/cadrumo/entrypoints/tui/ledger/actividad_asset_words.py, src/cadrumo/entrypoints/tui/ledger/registers_presentation.py, src/cadrumo/entrypoints/tui/modelo/, src/cadrumo/entrypoints/tui/aeat_sync/`.
- [ ] `P09.S53` - Switch CLI renderers that reword a served token to the served field; then delete their per-token sentences; `src/cadrumo/entrypoints/cli/`.

### Phase `P10` - protective check

A gate rejects new desktop tax wording once the families are served.

- [ ] `P10.S54` - Add a gate that rejects new desktop.* catalogue keys and window literals with tax meaning (tax states, reasons, boxes, modelos, periods, currency), with isolated fixtures proving it fires; run it in the desktop and quality gates; `dev/quality/tests/test_window_holds_no_tax_data.py, dev/locales/desktop_chrome.py`.

## Parallelization

Two sessions work each Step in order: the backend session serves the family and commits; the desktop frontend session then deletes the window copy and commits. A desktop deletion never starts before its backend Step's commit exists.

Steps whose backend owner modules are disjoint may run concurrently, across Phases as well as within one. Steps that share an owner module run in sequence. These share owners and must not run at once: P01.S01 and P02.S06 (`src/cadrumo/core/period.py`); P01.S01 and P02.S07 (`readiness_query.py`); P01.S02 and P06.S36 (`import_operation.py`); P03.S22 and P07.S46 (`export_operation.py`); P01.S03, P02.S08, P02.S09, P02.S10, P02.S16 and P06.S35 (`src/cadrumo/application/ledger/entry_options_operation.py`); P02.S07 and P06.S34 (`readiness_routes.py`); P02.S12 and P06.S38 (`catalogue_read_projection.py`); P02.S13, P06.S39 and P06.S40 (prorrata and capital goods owners); P02.S14, P06.S42 and P02.S15 with P06.S32 (activity asset owners); P03.S18, P03.S22, P07.S47 and P07.S48 (`work_form.py`); P03.S22 and P07.S45 (`iva_wallet_balance_operation.py`); P04.S24 and P08.S50 (`status_operation.py`); P05.S27 and P05.S28 (`sync_readiness.py`). P07.S47 follows P03.S18 to P03.S21. P09.S52 follows the P06 to P08 Steps it switches. P10.S54 runs last.

Locale catalogues are shared. Sessions commit `src/cadrumo/locales/*/common.yml` and `application.yml` whole, so commit each Step's catalogue change promptly, re-read the file before every edit and never hold uncommitted catalogue edits across another session's commit. The relay contract files and the operation contract manifest are also shared; regenerate and commit them in the same Step that changes them.

## Verification

Each Step that serves a family passes these checks, run from the worktree root:

- `just check-operation-contract-manifest` passes after `just generate-operation-contract-manifest` for any result contract change.
- Both relay checks pass: `uv run --no-sync python -B native/desktop/src-tauri/src/shell/ledger/relay_contracts.py --check` and `uv run --no-sync python -B native/desktop/src-tauri/src/shell/modelo/relay_contracts.py --check`.
- `just check-locales` passes, with every new `served` key translated in es, ca, en and hu.
- A real-operation test per locale runs the registered operation through its owner and asserts the served words, the `_words_language` value and the typed facts for each of es, ca, en and hu, including a refusal and an absent or unknown state.
- After each desktop deletion, `dev/quality/tests/test_window_holds_no_tax_data.py` passes and a grep of the deleted symbols in `native/desktop/frontend/src` and `native/desktop/src-tauri/src/shell` finds none.
- `just check-import-boundaries`, `just check-style`, `just check-format` and `just check-types` pass on the touched scope.

The plan is complete when every Step is closed, P10.S54's gate rejects a representative new desktop tax key and window literal in isolated fixtures, and the Phase-close and plan-close reviews pass.
