---
tags:
  - '#exec'
  - '#backend-served-surface'
date: '2026-11-03'
modified: '2026-11-04'
body_schema: 'body-v2'
body_hash: 'sha256:5c6913cc12d9b2edcec24027c64a827af974216954f291849cae69e51cd66997'
related:
  - "[[2026-11-03-backend-served-surface-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `backend-served-surface` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S01` `M` `src/cadrumo/core/period.py`
- `S01` `M` `src/cadrumo/application/ledger/entry_options_operation.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/entry_options_commands.py`
- `S01` `A` `src/cadrumo/application/ledger/period_options.py`
- `S01` `A` `src/cadrumo/entrypoints/cli/ledger_period_results.py`
- `S01` `A` `src/cadrumo/core/tests/test_period_calendar.py`
- `S01` `A` `src/cadrumo/application/ledger/tests/test_ledger_periods.py`
- `S01` `A` `src/cadrumo/entrypoints/cli/tests/test_ledger_period_results.py`
- `S01` `verify:` `uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_ledger_periods.py src/cadrumo/core/tests/test_period_calendar.py` -> `pass`
- `S01` `by:` `sonnet-executor`
- `S02` `M` `src/cadrumo/core/period.py`
- `S02` `M` `src/cadrumo/application/ledger/entry_options_operation.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/entry_options_commands.py`
- `S02` `A` `src/cadrumo/application/ledger/period_options.py`
- `S02` `A` `src/cadrumo/entrypoints/cli/ledger_period_results.py`
- `S02` `A` `src/cadrumo/core/tests/test_period_calendar.py`
- `S02` `A` `src/cadrumo/application/ledger/tests/test_ledger_periods.py`
- `S02` `A` `src/cadrumo/entrypoints/cli/tests/test_ledger_period_results.py`
- `S02` `verify:` `uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_ledger_periods.py src/cadrumo/core/tests/test_period_calendar.py` -> `pass`
- `S02` `by:` `sonnet-executor`
- `S03` `M` `src/cadrumo/application/ledger/entry_options_operation.py`
- `S03` `M` `src/cadrumo/domain/transactions/enums.py`
- `S03` `M` `src/cadrumo/application/ledger/tests/test_entry_options.py`
- `S03` `verify:` `uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_entry_options.py` -> `pass`
- `S03` `by:` `sonnet-executor`
- `S17` `A` `src/cadrumo/application/modelo/credit_resolution_words.py`
- `S17` `A` `src/cadrumo/application/modelo/disagreement_words.py`
- `S17` `A` `src/cadrumo/application/modelo/tests/test_work_form_served_actions.py`
- `S17` `M` `src/cadrumo/application/modelo/credit_resolution_contracts.py`
- `S17` `M` `src/cadrumo/application/modelo/credit_resolution_operation.py`
- `S17` `M` `src/cadrumo/application/modelo/work_form_issue_lines.py`
- `S17` `M` `src/cadrumo/application/modelo/work_form_notes.py`
- `S17` `M` `src/cadrumo/application/modelo/work_form_declaration_facts.py`
- `S17` `M` `src/cadrumo/application/modelo/calculation_notes.py`
- `S17` `M` `src/cadrumo/application/modelo/calculation_report.py`
- `S17` `M` `src/cadrumo/application/modelo/credit_resolution.py`
- `S17` `M` `src/cadrumo/entrypoints/cli/_modelo_work_disagreement_cli.py`
- `S17` `M` `src/cadrumo/locales/en/application.yml`
- `S17` `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_work_form_served_actions.py src/cadrumo/application/modelo/tests/test_calculation_note_wording.py` -> `pass`
- `S17` `by:` `sonnet-executor`
- `S31` `A` `src/cadrumo/application/ledger/staged_check_words.py`
- `S31` `A` `src/cadrumo/application/ledger/tests/test_staged_check_words.py`
- `S31` `M` `src/cadrumo/application/ledger/staged_check.py`
- `S31` `M` `src/cadrumo/application/ledger/staged_check_contracts.py`
- `S31` `M` `src/cadrumo/entrypoints/cli/staged_check_commands.py`
- `S31` `verify:` `uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_staged_check_words.py` -> `pass`
- `S31` `by:` `sonnet-executor`
- `S32` `A` `src/cadrumo/application/actividad_asset/served_words.py`
- `S32` `A` `src/cadrumo/application/actividad_asset/tests/test_served_words.py`
- `S32` `M` `src/cadrumo/application/actividad_asset/activity_asset_read_models.py`
- `S32` `M` `src/cadrumo/entrypoints/tui/ledger/actividad_asset_words.py`
- `S32` `verify:` `uv run --no-sync pytest src/cadrumo/application/actividad_asset/tests/test_served_words.py` -> `pass`
- `S32` `by:` `sonnet-executor`
- `S51` `M` `src/cadrumo/entrypoints/tui/ledger/registers_prorrata.py`
- `S51` `M` `src/cadrumo/entrypoints/tui/ledger/registers_capital_goods.py`
- `S51` `M` `src/cadrumo/entrypoints/tui/ledger/registers_inventory.py`
- `S51` `M` `src/cadrumo/entrypoints/tui/declarations/calendar.py`
- `S51` `M` `src/cadrumo/entrypoints/tui/declarations/controller.py`
- `S51` `M` `src/cadrumo/entrypoints/tui/ledger/evidence_files_review.py`
- `S51` `M` `src/cadrumo/application/operations/error_detail.py`
- `S51` `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/ledger/tests` -> `pass`
- `S51` `by:` `sonnet-executor`
- `S17` `M` `src/cadrumo/application/modelo/credit_resolution_repository.py`
- `S17` `M` `src/cadrumo/application/modelo/credit_resolution_words.py`
- `S17` `M` `src/cadrumo/application/modelo/disagreement_words.py`
- `S17` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S17` `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_100_credit_resolution_operation.py` -> `pass`
- `S01` `M` `dev/locales/desktop_ledger_catalogue_keys.py`
- `S01` `M` `native/desktop/frontend/.storybook/preview.tsx`
- `S01` `M` `native/desktop/frontend/scripts/ledger_contract.py`
- `S01` `M` `native/desktop/frontend/src/App.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/LedgerPage.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/LedgerPageDialogs.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/PeriodSelector.stories.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/PeriodSelector.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/documents/Documents.stories.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/inspector/DetailsSection.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/inspector/Inspector.stories.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/inspector/inspectorModel.ts`
- `S01` `M` `native/desktop/frontend/src/components/ledger/invoices/InvoicesSection.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/invoices/invoiceModel.ts`
- `S01` `M` `native/desktop/frontend/src/components/ledger/ledgerWords.ts`
- `S01` `M` `native/desktop/frontend/src/components/ledger/setup/ProrrataPane.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/setup/RatiosPane.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/setup/WithholdingPane.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/suggestions/SuggestionsProvider.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/transfer/ExportDialog.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/transfer/ImportDialog.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/transfer/importModel.ts`
- `S01` `M` `native/desktop/frontend/src/components/ledger/useLedgerPage.ts`
- `S01` `M` `native/desktop/frontend/src/dev/fixtures/ledgerEntryOptions.json`
- `S01` `M` `native/desktop/frontend/src/dev/ledgerFixture.ts`
- `S01` `M` `native/desktop/frontend/src/dev/ledgerSetupFixture.ts`
- `S01` `A` `native/desktop/frontend/src/dev/periodRecording.ts`
- `S01` `M` `native/desktop/frontend/src/dev/primitives/main.tsx`
- `S01` `M` `native/desktop/frontend/src/shell/ledger.ts`
- `S01` `M` `native/desktop/frontend/src/shell/ledgerContract.ts`
- `S01` `M` `native/desktop/frontend/src/shell/ledgerGrammar.ts`
- `S01` `M` `native/desktop/frontend/src/shell/ledgerImports.ts`
- `S01` `A` `native/desktop/frontend/src/shell/ledgerPeriods.ts`
- `S01` `M` `native/desktop/frontend/src/shell/ledgerPlan.ts`
- `S01` `M` `native/desktop/frontend/src/shell/ledgerSetup.ts`
- `S01` `M` `native/desktop/frontend/src/shell/ledgerYears.ts`
- `S01` `M` `native/desktop/frontend/tests/ledger-grammar.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/ledger-inspector-model.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/ledger-invoices-model.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/ledger-inspector.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/ledger-movements.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/ledger-served-vocabulary.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/ledger-shell.spec.ts`
- `S01` `A` `native/desktop/frontend/tests/support/servedPeriods.ts`
- `S01` `M` `native/desktop/frontend/tests/support/servedVocabulary.ts`
- `S01` `A` `src/cadrumo/application/ledger/tests/test_entry_options_period_recording.py`
- `S01` `M` `src/cadrumo/locales/ca/common.yml`
- `S01` `M` `src/cadrumo/locales/en/common.yml`
- `S01` `M` `src/cadrumo/locales/es/common.yml`
- `S01` `M` `src/cadrumo/locales/hu/common.yml`
- `S01` `verify:` `tsc/eslint/prettier` -> `pass`
- `S01` `verify:` `ledger-contract.mjs --check` -> `pass`
- `S01` `verify:` `relay_contracts.py --check` -> `pass`
- `S01` `verify:` `test_window_holds_no_tax_data + test_desktop_chrome` -> `pass`
- `S01` `verify:` `backend period tests` -> `pass`
- `S01` `verify:` `storybook:build` -> `pass`
- `S01` `verify:` `playwright ledger scenarios` -> `fail`
- `S01` `by:` `vaultspec-standard-executor`
- `S02` `M` `dev/locales/desktop_ledger_catalogue_keys.py`
- `S02` `M` `native/desktop/frontend/.storybook/preview.tsx`
- `S02` `M` `native/desktop/frontend/scripts/ledger_contract.py`
- `S02` `M` `native/desktop/frontend/src/App.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/LedgerPage.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/LedgerPageDialogs.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/PeriodSelector.stories.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/PeriodSelector.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/documents/Documents.stories.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/inspector/DetailsSection.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/inspector/Inspector.stories.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/inspector/inspectorModel.ts`
- `S02` `M` `native/desktop/frontend/src/components/ledger/invoices/InvoicesSection.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/invoices/invoiceModel.ts`
- `S02` `M` `native/desktop/frontend/src/components/ledger/ledgerWords.ts`
- `S02` `M` `native/desktop/frontend/src/components/ledger/setup/ProrrataPane.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/setup/RatiosPane.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/setup/WithholdingPane.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/suggestions/SuggestionsProvider.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/transfer/ExportDialog.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/transfer/ImportDialog.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/transfer/importModel.ts`
- `S02` `M` `native/desktop/frontend/src/components/ledger/useLedgerPage.ts`
- `S02` `M` `native/desktop/frontend/src/dev/fixtures/ledgerEntryOptions.json`
- `S02` `M` `native/desktop/frontend/src/dev/ledgerFixture.ts`
- `S02` `M` `native/desktop/frontend/src/dev/ledgerSetupFixture.ts`
- `S02` `A` `native/desktop/frontend/src/dev/periodRecording.ts`
- `S02` `M` `native/desktop/frontend/src/dev/primitives/main.tsx`
- `S02` `M` `native/desktop/frontend/src/shell/ledger.ts`
- `S02` `M` `native/desktop/frontend/src/shell/ledgerContract.ts`
- `S02` `M` `native/desktop/frontend/src/shell/ledgerGrammar.ts`
- `S02` `M` `native/desktop/frontend/src/shell/ledgerImports.ts`
- `S02` `A` `native/desktop/frontend/src/shell/ledgerPeriods.ts`
- `S02` `M` `native/desktop/frontend/src/shell/ledgerPlan.ts`
- `S02` `M` `native/desktop/frontend/src/shell/ledgerSetup.ts`
- `S02` `M` `native/desktop/frontend/src/shell/ledgerYears.ts`
- `S02` `M` `native/desktop/frontend/tests/ledger-grammar.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/ledger-inspector-model.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/ledger-invoices-model.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/ledger-inspector.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/ledger-movements.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/ledger-served-vocabulary.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/ledger-shell.spec.ts`
- `S02` `A` `native/desktop/frontend/tests/support/servedPeriods.ts`
- `S02` `M` `native/desktop/frontend/tests/support/servedVocabulary.ts`
- `S02` `A` `src/cadrumo/application/ledger/tests/test_entry_options_period_recording.py`
- `S02` `M` `src/cadrumo/locales/ca/common.yml`
- `S02` `M` `src/cadrumo/locales/en/common.yml`
- `S02` `M` `src/cadrumo/locales/es/common.yml`
- `S02` `M` `src/cadrumo/locales/hu/common.yml`
- `S02` `verify:` `tsc/eslint/prettier` -> `pass`
- `S02` `verify:` `ledger-contract.mjs --check` -> `pass`
- `S02` `verify:` `relay_contracts.py --check` -> `pass`
- `S02` `verify:` `test_window_holds_no_tax_data + test_desktop_chrome` -> `pass`
- `S02` `verify:` `backend period tests` -> `pass`
- `S02` `verify:` `storybook:build` -> `pass`
- `S02` `verify:` `playwright ledger scenarios` -> `fail`
- `S02` `by:` `vaultspec-standard-executor`
- `S01` `M` `native/desktop/frontend/src/components/modelo/workspace/CreditsPanel.tsx`
- `S01` `M` `native/desktop/frontend/src/components/modelo/workspace/IvaWalletDialog.tsx`
- `S01` `verify:` `tsc --noEmit` -> `pass`
- `S01` `verify:` `eslint/prettier --check` -> `pass`
- `S01` `verify:` `test_window_holds_no_tax_data` -> `pass`
- `S03` `M` `native/desktop/frontend/src/components/ledger/editing/MovementEditing.tsx`
- `S03` `M` `native/desktop/frontend/src/components/ledger/inspector/SplitDialog.tsx`
- `S03` `M` `native/desktop/frontend/src/components/ledger/movements/ClassifyDialog.tsx`
- `S03` `M` `native/desktop/frontend/src/components/ledger/movements/movementsModel.ts`
- `S03` `M` `native/desktop/frontend/src/shell/ledgerClassifications.ts`
- `S03` `M` `native/desktop/frontend/src/shell/ledgerCommands.ts`
- `S03` `M` `native/desktop/frontend/src/shell/ledgerSetup.ts`
- `S03` `verify:` `tsc --noEmit` -> `pass`
- `S03` `verify:` `eslint/prettier --check` -> `pass`
- `S03` `verify:` `test_window_holds_no_tax_data` -> `pass`
- `S03` `by:` `vaultspec-standard-executor`
- `S01` `M` `native/desktop/frontend/src/shell/ledgerMovementReads.ts`
- `S01` `M` `native/desktop/frontend/src/shell/ledgerPeriods.ts`
- `S01` `M` `dev/locales/desktop_chrome.py`
- `S01` `M` `dev/locales/desktop_ledger_workflow_keys.py`
- `S01` `M` `native/desktop/frontend/vite.config.ts`
- `S01` `verify:` `tsc --noEmit` -> `pass`
- `S01` `verify:` `ledger-contract.mjs --check` -> `pass`
- `S01` `verify:` `relay_contracts.py --check` -> `pass`
- `S01` `verify:` `window guard + test_desktop_chrome + recording tests` -> `pass`
- `S01` `verify:` `storybook:build` -> `pass`
- `S01` `verify:` `playwright ledger scenarios` -> `pass`
- `S03` `M` `dev/locales/desktop_chrome.py`
- `S03` `M` `dev/locales/desktop_ledger_workflow_keys.py`
- `S03` `M` `native/desktop/frontend/scripts/ledger_contract.py`
- `S03` `M` `native/desktop/frontend/src/shell/ledgerContract.ts`
- `S03` `M` `native/desktop/frontend/src/shell/ledgerGrammar.ts`
- `S03` `M` `src/cadrumo/locales/ca/common.yml`
- `S03` `M` `src/cadrumo/locales/en/common.yml`
- `S03` `M` `src/cadrumo/locales/es/common.yml`
- `S03` `M` `src/cadrumo/locales/hu/common.yml`
- `S03` `verify:` `tsc --noEmit` -> `pass`
- `S03` `verify:` `ledger-contract.mjs --check` -> `pass`
- `S03` `verify:` `relay_contracts.py --check` -> `pass`
- `S03` `verify:` `window guard + test_desktop_chrome + recording tests` -> `pass`
- `S03` `verify:` `storybook:build` -> `pass`
- `S31` `M` `dev/locales/desktop_chrome.py`
- `S31` `M` `dev/locales/desktop_ledger_workflow_keys.py`
- `S31` `M` `native/desktop/frontend/src/components/ledger/editing/ReviewBlockers.tsx`
- `S31` `M` `native/desktop/frontend/src/components/ledger/suggestions/SuggestionsProvider.tsx`
- `S31` `M` `native/desktop/frontend/src/dev/fixtures/ledgerStagedCheck.json`
- `S31` `M` `native/desktop/frontend/src/dev/ledgerStagedCheckFixture.ts`
- `S31` `M` `native/desktop/frontend/src/shell/ledger.ts`
- `S31` `A` `native/desktop/frontend/src/shell/ledgerLanguage.ts`
- `S31` `M` `native/desktop/frontend/src/shell/ledgerPlan.ts`
- `S31` `M` `native/desktop/frontend/src/shell/ledgerStagedCheck.ts`
- `S31` `M` `native/desktop/frontend/tests/ledger-plan.spec.ts`
- `S31` `M` `native/desktop/frontend/tests/ledger-staged-check-session.spec.ts`
- `S31` `M` `native/desktop/frontend/tests/support/stagedCheck.ts`
- `S31` `M` `src/cadrumo/application/ledger/tests/test_staged_check_recording.py`
- `S31` `M` `src/cadrumo/locales/ca/common.yml`
- `S31` `M` `src/cadrumo/locales/en/common.yml`
- `S31` `M` `src/cadrumo/locales/es/common.yml`
- `S31` `M` `src/cadrumo/locales/hu/common.yml`
- `S31` `verify:` `tsc --noEmit` -> `pass`
- `S31` `verify:` `ledger-contract.mjs --check` -> `pass`
- `S31` `verify:` `relay_contracts.py --check` -> `pass`
- `S31` `verify:` `window guard + test_desktop_chrome + recording tests` -> `pass`
- `S31` `verify:` `storybook:build` -> `pass`
- `S31` `verify:` `playwright ledger scenarios` -> `pass`
- `S31` `by:` `vaultspec-standard-executor`

## Notes

- `S01` backend half 3ad00c7b9d; locale keys and `ledger_results` periods line landed in 8118f456c0; desktop deletion pending; parsePeriodCode, four-digit year rule and Rust `BORRADOR_PERIOD` not yet covered
- `S02` backend half 3ad00c7b9d; locale keys and `ledger_results` periods line landed in 8118f456c0; desktop deletion pending; parsePeriodCode, four-digit year rule and Rust `BORRADOR_PERIOD` not yet covered
- `S03` backend half f9cac4d993, f7050b43ad; CLI result schema fix pending; desktop half by frontend session
- `S17` backend half 4bca1631ba and a4282f6373; desktop modeloContract.ts and fixtures need regeneration by the frontend session
- `S03` round 2 b0bd26b508: `carries_business_figures,` `keeps_category,` `takes_usage_ratio` and the CLI entry-options result schema; window half b3a41c4296 plus pending deletion of the round-2 constants
- `S31` backend 8118f456c0; desktop must re-record ledgerStagedCheck.json `(CADRUMO_STAGED_CHECK_UNRECORDED=all)` and delete ReviewBlockers token map
- `S32` backend and TUI 92f903aa62; desktop deletion of `GAP_KEYS,` `LEFT_OUT_KEYS,` `NO_TABLE_MINIMUM` and asset reason words pending; baja summary and field labels not served
- `S51` items 1-5 committed (047a35a89d, capital goods, 7165206c6c, d226fad0ee, evidence block reasons); items 6 IVA rate error and 7 invoice ES/EUR defaults open; TUI advisory map and refusal field labels remain
- `S17` round 3 2c85394de5: state, current, revocable and lead words; locale hunks landed in another session's commit; agent ran a repo-wide ruff --fix around 16:30
- `S01` Window half in 15552776ca. Kept parsePeriodCode, isPeriodCode and `LEDGER_PERIOD_SPANS` until the modelo IVA wallet and credits callers migrate. Unserved periods read as unknown. 8 ledger scenario failures (combobox/popover/pointer interception) are unclassified; evidence is with CHECKS. desktop-frontend-chrome was not rebuilt during the CHECKS hold.
- `S02` Window half in 15552776ca. Kept parsePeriodCode, isPeriodCode and `LEDGER_PERIOD_SPANS` until the modelo IVA wallet and credits callers migrate. Unserved periods read as unknown. 8 ledger scenario failures (combobox/popover/pointer interception) are unclassified; evidence is with CHECKS. desktop-frontend-chrome was not rebuilt during the CHECKS hold.
- `S01` fa183e95b1 moves the modelo wallet callers to the served periods store. Playwright and Storybook were not run (CHECKS source-only release). parsePeriodCode, isPeriodCode and `LEDGER_PERIOD_SPANS` remain until ledger-grammar.spec, ledgerPeriods.ts and ledgerMovementReads.ts stop using them and the contract regen is released.
- `S03` 18bebf5982 (round 2): the window reads served `carries_business_figures,` `keeps_category` and `takes_usage_ratio,` with unknown kept as null. `BUSINESS_BEARING_CLASSIFICATIONS` and isBusinessBearing in the generated ledgerContract.ts await the held regen. When unserved, the business-expenses view does not narrow (a superset). Playwright was not run (CHECKS source-only release).
- `S01` 71ba964575 deletes parsePeriodCode and isPeriodCode. `LEDGER_PERIOD_SPANS,` LedgerPeriodCode and the `_periods()` block in `scripts/ledger_contract.py,` plus the producerless `period_unknown` refusal key, await the held regen and locale release.
- `S01` 3bc2680f55 regenerated ledgerContract.ts without the `_periods()` block `(LEDGER_PERIOD_SPANS,` LedgerPeriodCode) and removed the producerless `period_unknown` key. e72b1ed685 fixes the 8 ledger scenario failures: the uncommitted package-lock refresh left duplicate nested Radix copies (focus-scope, dismissable-layer, focus-guards, portal, presence); vite resolve.dedupe is a workaround until the dependency owner dedupes. Ledger scenarios 315/316; ledger-setup:1944 failed once and passed alone, cause unproven. desktop-frontend-chrome not yet rebuilt.
- `S03` 3bc2680f55 deleted the business-bearing `_CLASSIFICATION_SETS` entry and regenerated, so no window copy of the three classification rules remains.
- `S31` 77ce7ce3af renders served blocker words and fix words plus the share refusal words; deletes six window blocker sentences; the fixture is re-recorded by `test_staged_check_recording.` Still window-held, as unserved gaps: `sealed_unread,` `suggestion_*,` `action_and_edits,` `exclude_and_classification,` `actions_conflict.`
