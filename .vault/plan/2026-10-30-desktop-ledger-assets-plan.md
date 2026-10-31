---
tags:
  - '#plan'
  - '#desktop-ledger-assets'
date: '2026-10-30'
tier: L1
related:
  - '[[2026-10-23-desktop-ledger-editor-adr]]'
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-09-21-assets-core-lifecycle-contract-adr]]'
  - '[[2026-09-23-assets-core-amortization-method-set-adr]]'
  - '[[2026-10-30-desktop-ledger-assets-reference]]'
modified: '2026-10-31'
body_schema: body-v2
body_hash: 'sha256:8ba4da8b6f2abd4de8292de3204b3aea1eba9e375ab214f4e17eb2cd0b0f5dc4'
---

# `desktop-ledger-assets` plan

## Description

Approved 2026-10-30. Basis: the operator's direct instruction to this session (CADRUMO-AMORTIZATION-UX) to implement the React and thin Rust side of adding, editing and removing assets and inventory items in a new Ledger tab, and to audit how the amortization schedule and timeline are displayed and logged. The operator proposed the tab name Assets, placed before the Setup menu.

The design is `2026-10-30-desktop-ledger-assets-reference`. `2026-10-23-desktop-ledger-editor-adr` governs host admission and write states, and adding operation ids amends it at S05. `2026-10-05-desktop-design-system-adr` governs S01 to S04 and S06. The two assets-core ADRs bound what the views may claim. No business logic enters React or Rust. No new costly decision is involved; the backend contracts come from `2026-10-30-assets-core-plan` S06, S11 and S12.

Inventory edit and remove have no backend operation and no owner; this was raised with the operator on 2026-10-30 and is unanswered. S06 ships only what the registered operations allow unless that changes.

## Steps

- [x] `S01` - Lay the foundation: provisional contract module, words, YearStepper, synthetic fixtures and the RightPanel width prop; `native/desktop/frontend/src/components/ledger/assets/, native/desktop/frontend/src/dev/assetsFixture.ts`.
- [x] `S02` - Build the Assets section shell, element list, detail panel and filing handoff, in stories only; `native/desktop/frontend/src/components/ledger/assets/AssetsSection.tsx, FixedAssetsPane.tsx, AssetList.tsx, AssetDetail.tsx`.
- [x] `S03` - Build the amortization plan and append-only timeline views, in stories only; `native/desktop/frontend/src/components/ledger/assets/AmortizationPlan.tsx, AssetTimeline.tsx`.
- [x] `S04` - Build the options-driven forms for element, descriptor, correction, claim and baja, covering every write state; `native/desktop/frontend/src/components/ledger/assets/AssetForm.tsx, DescribeForm.tsx, CorrectForm.tsx, ClaimFlow.tsx, BajaForm.tsx`.
- [x] `S05` - Conform to the landed S06, S11 and S12 contracts, amend the ledger editor ADR, admit the new ids and delete the provisional module; `native/desktop/frontend/src/components/ledger/assets/, native/desktop/src-tauri/src/shell/ledger/admitted.rs, .vault/adr/`.
- [x] `S06` - Build the Existencias panel, run valuation preview as a held write, add the assets tab before Setup and retire the Setup panes; `native/desktop/frontend/src/components/ledger/assets/InventoryPanel.tsx, native/desktop/frontend/src/components/ledger/setup/RegistersSection.tsx, ledgerWords.ts, layout.ts`.
- [ ] `S07` - Review the integrated tab in the running app and append findings to the audit; `.vault/audit/`.

## Parallelization

S01 comes first. S02, S03 and S04 then run in parallel with disjoint files; string keys go to the S01 owner, who holds the strings file and fixtures. S05 waits on the backend contracts and lands with the manifest change in one step coordinated with CADRUMO-AMORTIZATION2. S06 follows S05, because the tab ships only when its operations are real. S07 is last. Other sessions share this worktree, so commits name explicit paths.

## Verification

A person can add an element, set its name and serial, correct it, record and supersede a dotacion, give it a baja, and read its plan and timeline in the running desktop window, through registered operations only. Stories cover every state in the reference, including a decades-spanning ledger. A missing claim never reads as zero or a refusal, and an unknown write pauses writes and is never resent. No method, rate or year list exists in React or Rust. Frontend tests, typecheck, the Rust admission test and the locale gates pass, and the integrated review passes.
