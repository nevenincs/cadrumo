---
tags:
  - '#exec'
  - '#desktop-ledger-assets'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:451ae5e11694542c42a1bbecdf80eb39fc1e213130361a7d87b94c801db1f571'
related:
  - "[[2026-10-30-desktop-ledger-assets-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `desktop-ledger-assets` ledger

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

- `S01` `A` `native/desktop/frontend/src/components/ledger/assets/assetsContract.ts`
- `S01` `A` `native/desktop/frontend/src/components/ledger/assets/assetsWords.ts`
- `S01` `A` `native/desktop/frontend/src/components/ledger/assets/YearStepper.tsx`
- `S01` `A` `native/desktop/frontend/src/components/ledger/assets/YearStepper.stories.tsx`
- `S01` `A` `native/desktop/frontend/src/dev/assetsFixture.ts`
- `S01` `A` `native/desktop/frontend/tests/ledger-assets-contract.spec.ts`
- `S01` `M` `native/desktop/frontend/src/dev/ledgerSetupFixture.ts`
- `S01` `M` `native/desktop/frontend/src/dev/ledgerFixture.ts`
- `S01` `M` `native/desktop/frontend/src/dev/ledgerClassesFixture.ts`
- `S01` `M` `native/desktop/frontend/src/components/ledger/inspector/RightPanel.tsx`
- `S01` `M` `dev/locales/desktop_ledger_workflow_keys.py`
- `S01` `M` `src/cadrumo/locales/en/common.yml`
- `S01` `M` `src/cadrumo/locales/es/common.yml`
- `S01` `M` `src/cadrumo/locales/ca/common.yml`
- `S01` `M` `src/cadrumo/locales/hu/common.yml`
- `S01` `verify:` `tsc --noEmit` -> `pass`
- `S01` `verify:` `eslint on S01 paths` -> `pass`
- `S01` `verify:` `prettier --check on S01 paths` -> `pass`
- `S01` `verify:` `playwright (no-server config) ledger-assets-contract, ledger-classes, ledger-fixture-host, ledger-setup-model, ledger-apply, ledger-plan, ledger-stage, ledger-window, ledger-grammar, ledger-inspector-model, ledger-invoices-model, ledger-documents-model` -> `pass`
- `S01` `verify:` `pytest dev/locales/tests/test_desktop_chrome.py test_no_key_shadows_a_namespace.py test_reserved_translation_tokens.py` -> `pass`
- `S01` `verify:` `pytest dev/locales/tests (honesty, hungarian, spelling, english spelling, quoted keys, scaffold, navigation labels)` -> `pass`
- `S01` `by:` `implementation-engineer`
- `S02` `A` `native/desktop/frontend/src/components/ledger/assets/AssetsSection.tsx`
- `S02` `A` `native/desktop/frontend/src/components/ledger/assets/FixedAssetsPane.tsx`
- `S02` `A` `native/desktop/frontend/src/components/ledger/assets/AssetList.tsx`
- `S02` `A` `native/desktop/frontend/src/components/ledger/assets/AssetDetail.tsx`
- `S02` `A` `native/desktop/frontend/src/components/ledger/assets/FilingHandoffPanel.tsx`
- `S02` `A` `native/desktop/frontend/src/components/ledger/assets/Assets.stories.tsx`
- `S02` `verify:` `eslint+prettier on the six files` -> `pass`
- `S02` `by:` `implementer`
- `S03` `A` `native/desktop/frontend/src/components/ledger/assets/AmortizationPlan.tsx`
- `S03` `A` `native/desktop/frontend/src/components/ledger/assets/AssetTimeline.tsx`
- `S03` `A` `native/desktop/frontend/src/components/ledger/assets/planWords.ts`
- `S03` `A` `native/desktop/frontend/src/components/ledger/assets/planRead.ts`
- `S03` `A` `native/desktop/frontend/src/components/ledger/assets/Amortization.stories.tsx`
- `S03` `M` `native/desktop/frontend/src/dev/assetsFixture.ts`
- `S03` `verify:` `npx tsc --noEmit` -> `pass`
- `S03` `verify:` `npx eslint owned paths` -> `pass`
- `S03` `verify:` `npx prettier --check owned paths` -> `pass`
- `S03` `by:` `implementer`
- `S04` `A` `native/desktop/frontend/src/components/ledger/assets/AssetForm.tsx`
- `S04` `A` `native/desktop/frontend/src/components/ledger/assets/DescribeForm.tsx`
- `S04` `A` `native/desktop/frontend/src/components/ledger/assets/CorrectForm.tsx`
- `S04` `A` `native/desktop/frontend/src/components/ledger/assets/ClaimFlow.tsx`
- `S04` `A` `native/desktop/frontend/src/components/ledger/assets/BajaForm.tsx`
- `S04` `A` `native/desktop/frontend/src/components/ledger/assets/assetWrites.ts`
- `S04` `A` `native/desktop/frontend/src/components/ledger/assets/AssetForms.stories.tsx`
- `S04` `M` `native/desktop/frontend/src/components/ledger/assets/assetsContract.ts`
- `S04` `M` `native/desktop/frontend/src/dev/assetsFixture.ts`
- `S04` `M` `native/desktop/frontend/src/dev/ledgerSetupFixture.ts`
- `S04` `M` `native/desktop/frontend/tests/ledger-assets-contract.spec.ts`
- `S04` `verify:` `tsc --noEmit` -> `pass`
- `S04` `verify:` `eslint on S04 paths` -> `pass`
- `S04` `verify:` `prettier --check on S04 paths` -> `pass`
- `S04` `verify:` `playwright (no-server config) ledger-assets-contract, ledger-setup-model, ledger-fixture-host, ledger-classes, ledger-grammar, ledger-stage, ledger-apply, ledger-plan, ledger-window, ledger-inspector-model, ledger-invoices-model, ledger-documents-model` -> `pass`
- `S04` `by:` `implementation-engineer`
- `S05` `A` `native/desktop/frontend/src/components/ledger/assets/assetFields.ts`
- `S05` `A` `native/desktop/frontend/src/dev/assetsSeed.ts`
- `S05` `A` `dev/locales/desktop_assets_keys.py`
- `S05` `A` `dev/locales/tests/test_desktop_asset_vocabulary.py`
- `S05` `A` `dev/registry/tests/test_desktop_asset_seed_follows_the_table.py`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/Amortization.stories.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/AmortizationPlan.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/AssetDetail.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/AssetForm.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/AssetForms.stories.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/AssetList.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/AssetTimeline.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/Assets.stories.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/AssetsSection.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/BajaForm.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/ClaimFlow.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/CorrectForm.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/FilingHandoffPanel.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/FixedAssetsPane.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/assetWrites.ts`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/assetsContract.ts`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/assetsWords.ts`
- `S05` `M` `native/desktop/frontend/src/components/ledger/assets/planWords.ts`
- `S05` `M` `native/desktop/frontend/src/components/ledger/inspector/RightPanel.tsx`
- `S05` `M` `native/desktop/frontend/src/components/ledger/setup/AssetsPane.tsx`
- `S05` `M` `native/desktop/frontend/src/dev/assetsFixture.ts`
- `S05` `M` `native/desktop/frontend/src/dev/ledgerSetupFixture.ts`
- `S05` `M` `native/desktop/frontend/src/shell/ledgerSetup.ts`
- `S05` `M` `native/desktop/frontend/src/shell/strings.ts`
- `S05` `M` `native/desktop/frontend/tests/ledger-assets-contract.spec.ts`
- `S05` `M` `dev/locales/desktop_chrome.py`
- `S05` `M` `dev/locales/desktop_ledger_workflow_keys.py`
- `S05` `M` `src/cadrumo/locales/en/common.yml`
- `S05` `M` `src/cadrumo/locales/es/common.yml`
- `S05` `M` `src/cadrumo/locales/ca/common.yml`
- `S05` `M` `src/cadrumo/locales/hu/common.yml`
- `S05` `verify:` `npx tsc --noEmit` -> `pass`
- `S05` `verify:` `ledger-assets-contract.spec` -> `pass`
- `S05` `by:` `implementation-engineer`
- `S05` `A` `native/desktop/frontend/src/components/ledger/assets/DisposalFigures.tsx`
- `S05` `M` `dev/locales/desktop_assets_keys.py`
- `S05` `M` `dev/locales/tests/test_desktop_asset_vocabulary.py`
- `S05` `M` `dev/registry/tests/test_desktop_asset_seed_follows_the_table.py`
- `S05` `M` `native/desktop/frontend/src/dev/assetsSeed.ts`
- `S06` `M` `native/desktop/frontend/src/shell/layout.ts`
- `S06` `M` `native/desktop/frontend/src/components/ledger/ledgerWords.ts`
- `S06` `M` `native/desktop/frontend/src/components/ledger/LedgerPage.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/LedgerPage.stories.tsx`
- `S06` `M` `native/desktop/frontend/src/App.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/setup/RegistersSection.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/setup/Setup.stories.tsx`
- `S06` `D` `native/desktop/frontend/src/components/ledger/setup/AssetsPane.tsx`
- `S06` `M` `native/desktop/frontend/tests/scenarios/ledger-setup.spec.ts`
- `S06` `M` `native/desktop/frontend/tests/scenarios/ledger-sweep.spec.ts`
- `S06` `M` `dev/locales/desktop_chrome.py`
- `S06` `M` `dev/locales/desktop_ledger_workflow_keys.py`
- `S06` `M` `dev/locales/desktop_ledger_catalogue_keys.py`
- `S06` `M` `src/cadrumo/locales/en/common.yml`
- `S06` `M` `src/cadrumo/locales/es/common.yml`
- `S06` `M` `src/cadrumo/locales/ca/common.yml`
- `S06` `M` `src/cadrumo/locales/hu/common.yml`
- `S06` `verify:` `pytest dev/locales/tests/test_desktop_chrome.py dev/locales/tests/test_parity.py` -> `pass`
- `S06` `verify:` `eslint+prettier on changed frontend paths` -> `pass`
- `S06` `by:` `implementer`
- `S06` `M` `native/desktop/frontend/tests/scenarios/about.spec.ts`
- `S06` `M` `native/desktop/frontend/tests/scenarios/ledger-pause.spec.ts`
- `S06` `verify:` `uv run --no-sync pytest dev/locales/tests/test_desktop_chrome.py dev/locales/tests/test_parity.py dev/locales/tests/test_hungarian_dictionary.py dev/locales/tests/test_spelling_lexicon.py -q` -> `pass`
- `S06` `verify:` `cmake --build build/windows-x64 --target desktop-frontend-chrome` -> `pass`
- `S06` `by:` `implementation-engineer`
- `S06` `M` `native/desktop/frontend/src/components/AboutDialog.tsx`
- `S06` `M` `native/desktop/frontend/src/components/AttendanceRequests.tsx`
- `S06` `M` `native/desktop/frontend/src/components/LanguageSelect.tsx`
- `S06` `M` `native/desktop/frontend/src/components/account/CreateProfile.tsx`
- `S06` `M` `native/desktop/frontend/src/components/agent/SkillDialog.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/documents/DocumentPanels.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/documents/DocumentsSection.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/documents/DocumentViewer.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/documents/DraftReview.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/documents/EvidenceRecords.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/inspector/ActionDialog.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/inspector/ModelSuggestion.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/inspector/SelectionInspector.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/inspector/inspectorWords.ts`
- `S06` `M` `native/desktop/frontend/src/components/ledger/invoices/InvoiceEditor.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/invoices/InvoicesSection.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/matching/MatchQueue.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/setup/HealthSection.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/setup/setupWords.ts`
- `S06` `M` `native/desktop/frontend/src/components/ledger/transfer/ExportDialog.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/transfer/ImportDialog.tsx`
- `S06` `M` `native/desktop/frontend/src/components/ledger/transfer/transferWords.ts`
- `S06` `M` `native/desktop/frontend/src/components/modelo/declarations/DeclarationsPage.tsx`
- `S06` `M` `native/desktop/frontend/src/components/modelo/declarations/NewDeclarationDialog.tsx`
- `S06` `M` `native/desktop/frontend/src/components/modelo/declarations/declarationsWords.ts`
- `S06` `M` `native/desktop/frontend/src/components/modelo/workspace/CorrectionDialog.tsx`
- `S06` `M` `native/desktop/frontend/src/components/modelo/workspace/WorkspaceScreen.tsx`
- `S06` `M` `native/desktop/frontend/tests/scenarios/language.spec.ts`
- `S06` `M` `native/desktop/frontend/tests/scenarios/profiles.spec.ts`
- `S06` `M` `native/desktop/frontend/tests/scenarios/scenarios.spec.ts`
- `S06` `M` `native/desktop/frontend/tests/scenarios/ledger-shell.spec.ts`
- `S06` `M` `native/desktop/frontend/tests/scenarios/modelo.spec.ts`
- `S06` `M` `native/desktop/frontend/tests/scenarios/agent-skills.spec.ts`
- `S06` `M` `native/desktop/frontend/src/components/ledger/inspector/inspectorWords.ts`
- `S06` `M` `dev/locales/desktop_ledger_document_keys.py`
- `S06` `verify:` `npx eslint and npx prettier --check on the changed frontend files` -> `pass`
- `S06` `by:` `implementer-standard`

## Notes

- `S01` `test_parity.py::test_codebase_to_locale_parity` fails on six `ledger.actividad_asset.errors.*` keys other sessions hold uncommitted in the four common.yml catalogues; no desktop.ledger.assets key is named in it
- `S01` The four common.yml catalogues carry other sessions' uncommitted keys beside the 107 desktop.ledger.assets keys of this Step; they are not in this Step's commit
- `S02` tsc reports errors only in src/dev/assetsFixture.ts, written by another Step in progress; none in these files
- `S03` assetsFixture.ts holds another session's uncommitted hunks; only the S03 hunks were staged
- `S04` S04 The new string keys the forms use are not yet in the locale catalogues or dev/locales; the locale gates fail on them until the strings owner adds them
- `S04` S04 assetsFixture.ts also carries uncommitted pending-figure edits made for the plan views
- `S04` S04 ledgerSetupFixture.ts gains one argument so the admitted create, correct, claim and forecast keep answering their admitted shapes
- `S05` Corrective conformance to the landed backend tokens; S05 not closed, host admission waits. Uncommitted: shared files hold another session's edits.
- `S05` Conformed to the served years, keys, class labels and the baja operations; S05 not closed. Uncommitted: shared files hold another session's edits.
- `S06` Scenario specs ledger-setup and ledger-sweep not run: they need the served scenario bundle, and assets/StockPane.tsx did not exist yet (tsc fails only on that import).
- `S06` tsc reports only another Step's tests/ledger-assets-contract.spec.ts unused port; desktop-frontend-chrome build refuses on `desktop.ledger.stock.field.*` keys not yet declared (another Step); locale pytest fails only on `desktop.ledger.assets.year_estimated*` undeclared (another Step)
