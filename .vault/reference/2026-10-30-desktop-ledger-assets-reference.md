---
tags:
  - '#reference'
  - '#desktop-ledger-assets'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:a62e3cc1ace57a8abadaa96a606f6dadb2674981af4319e42d0984c337fa4f8e'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace desktop-ledger-assets with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `desktop-ledger-assets` reference: `assets tab design and schedule display audit`

Design for the Assets tab, from a read-only architecture pass over the desktop frontend, the host admission list and the activity-asset backend. Nothing was run. `FE` is `native/desktop/frontend/src`. Backend field names are provisional until `2026-10-30-assets-core-plan` S12 lands.

## Summary

### Information architecture

- `assets` is the fourth entry of `TAB_SECTIONS` (`FE/components/ledger/ledgerWords.ts:14`), which places it before Setup (`FE/components/ledger/LedgerHeader.tsx:135`). It has no period selector (`FE/components/ledger/LedgerPage.tsx:187`), and its selection and year are never persisted (`FE/shell/layout.ts:56`).
- The body is `SetupTabs` with `owner="ledger/assets"` and areas Inmovilizado and Existencias (`FE/components/ledger/setup/SetupParts.tsx:124`).
- Inmovilizado: icon toolbar (add, `YearStepper`, summary pills), element list, detail in `RightPanel`. The detail header holds name, serial, marks and one icon button per act; its tabs are Plan, Timeline and Ficha. The filing handoff is a read-only folding `Panel` under the list.
- Existencias: one table of books for the selected year, with add book, add movement, closing authority and valuation.
- `AssetsPane.tsx` and `InventoryPane.tsx` are deleted and their areas removed from `FE/components/ledger/setup/RegistersSection.tsx:11`. Capital goods stays. The three registers never merge.
- `YearStepper` is `IconButton`, `NativeSelect`, `IconButton`, with options only from years the backend or ledger reports. `PeriodSelector` does not fit: it caps years (`FE/shell/ledgerGrammar.ts:333`) and has a second stepper in its popover. The stepper imposes no bounds; the backend refuses.

### Units

All paths are under `FE/components/ledger/assets/` unless stated.

- S01: `assetsContract.ts`, `assetsWords.ts`, `YearStepper.tsx`, `FE/dev/assetsFixture.ts`, the `FE/dev/ledgerSetupFixture.ts` composition line, the strings file `dev/locales/desktop_ledger_workflow_keys.py` and one additive `RightPanel` default-width prop.
- S02: `AssetsSection.tsx`, `FixedAssetsPane.tsx`, `AssetList.tsx`, `AssetDetail.tsx`, `FilingHandoffPanel.tsx`, stories.
- S03: `AmortizationPlan.tsx`, `AssetTimeline.tsx`, `planWords.ts`, stories.
- S04: `AssetForm.tsx`, `DescribeForm.tsx`, `CorrectForm.tsx`, `ClaimFlow.tsx`, `BajaForm.tsx`, `assetWrites.ts`, stories.
- S06: `InventoryPanel.tsx`, the moved `JsonDocumentField`, and the shared edits to `layout.ts`, `ledgerWords.ts`, `LedgerPage.tsx`, `windowViews.ts`, `RegistersSection.tsx`, `Setup.stories.tsx`.
- S05: `FE/shell/ledger.ts`, `FE/shell/ledgerSetup.ts`, `native/desktop/src-tauri/src/shell/ledger/admitted.rs`, `relay_contracts.json`, and the ADR amendment.

Reused: `Panel`, `SetupTable` (the name cell is a button, as the table has no row click), `TextField`, `ChoiceField`, `FormGrid`, `CallLine`, `useSetupRead`, `useSetupWrite`, `readLanding`, `useSetupDraft`, `WriteHold`, `PausedBanner`, `setupCall`, `rankDecimal`, `amountText`, `dateText`, `AttentionMark` and `GlyphMark` (`FE/components/modelo/workspace/Marks.tsx:42`). New: `YearStepper`, the options-driven form renderer, the plan and timeline views.

### Provisional contract

All shapes live in `assetsContract.ts`. An amount is `PublicDecimal | null`, and null is unknown, never zero.

- `AssetListResult`: `rows`, `years`.
- `AssetListRow`: `asset_id`, `name`, `serial`, `kind_key`, `method_key`, `in_service_date`, `revision_number`, optional `baja` (`date`, `reason_key`), `counts` (`missing`, `incomplete`, `conflict`, `stale`).
- `PlanRow`: `tax_year`, `state_key`, `finding_keys`, `authority` (`edition`, `projected`), `election` (`fingerprint`, `method_key`, `revision_number`), `service_days`, `calendar_days`, `planned`, `planned_absent_key`, `claimed`, `pending_end`, `claimable` (`from`, `until`, nullable), `claims`.
- `PlanClaim`: `claim_id`, `amount`, `from`, `until`, `effective`, `superseded_by`, `revision_number`, `matches_current_schedule`, `used_by`.
- `TimelineEvent`: `sequence`, `recorded_at` (nullable), `type_key`, `origin_key`, `effect_date`, `replaces_sequence`, `changes` (`field_key`, `before`, `after`), `affects_calculation`.
- `FormOptions`: `kind`, `tax_year`, `fields` (`key`, `label_key`, `control`, `required`, `choices` of `token` and `label_key`, `bounds`).
- `Descriptor`: `asset_id`, `sequence`, `name`, `serial`, `fields`.

The module exports `PROVISIONAL_OPERATIONS` and one `submitProvisional`, the only cast to `LedgerDefinitionId`. Draft ids cannot enter `LEDGER_DEFINITIONS` early, because the mirror check and the admission test fail (`dev` `relay_contracts.py:51`, `native/desktop/src-tauri/src/shell/ledger/admitted.rs:186`). A unit test fails once a provisional id appears in `LEDGER_DEFINITIONS`. No flags or TODOs; fixtures stay in `FE/dev`. Conforming moves the types to `ledgerSetup.ts` and deletes the module, so the compiler lists every consumer. The tab ships only at S06; until then it exists in stories, so production never shows a fixture or a `not_admitted` tab. Fixtures include a decades-spanning ledger and every state below.

### Schedule and timeline audit

The plan answers, per tax year, what the schedule allows now, what is recorded as effective, and what is pending. It is current and recomputable, and React computes nothing in it. The timeline answers what was appended, in what order, from where, and what it replaced. It is history, never recalculated.

- Planned and claimed: two columns, never one amount.
- Missing: alert glyph, a word and a dash under claimed, with the planned accrual beside it. Non-blocking; it disables nothing.
- Recorded zero: `0,00`, a real claim (`src/cadrumo/domain/renta/actividad_asset/claims.py:79`), distinct from missing.
- Unknown or incomplete: a dash plus the backend's absent key. Missing opening history is not zero.
- Free method: no planned figure, with its own word; the elected amount shows only once claimed.
- Partial year: claimed intervals and days are shown and the gap is named.
- Superseded claim: excluded from claimed. Expanding the year lists all claims, each with glyph and word and a pointer to its replacement. Colour alone never carries it.
- Correction: rows show the revision each claim was recorded under and `matches_current_schedule`.
- Method change: rows state their own election, with a divider where the fingerprint changes.
- Projected authority: a mark on the row. It serves forecast and Modelo 130, and the row says Modelo 100 is unavailable for that year.
- Descriptor change: timeline only, labelled as not affecting the calculation.
- Baja: marks the row and the list, with no planned rows after it. History stays and the element stays listed.

Append-only presentation: fixed sequence order with sorting disabled. Verbs say added or recorded (correction added, description added, dotacion recorded, baja recorded), and "edited" never appears. An earlier event is never restyled or rewritten; "replaced by" sits in its own column. Before and after values come from the backend, never a diff in React. A null `recorded_at` reads as time not recorded. Recording date and effect date are separate columns. Forecasts, findings and reads are not events. Nothing from either view reaches logs, storage or diagnostics.

### Edit and remove semantics

There is no single Edit button and no trash icon.

- Edit record (name, serial, libro registro fields): `describe` appends a descriptor. No revision, nothing goes stale.
- Correct (tax facts or method): `correct` appends a superseding revision, with superseding claims applied atomically in one operation. Method changes apply only from a tax-year boundary.
- Record dotacion: `forecast`, then `claim`. The forecast shows first, and `creating_operation` is not on the form.
- Correct dotacion: the same flow with `supersedes_claim_id`.
- Baja: `dispose` with date and reason, history kept. A wrongly created element also leaves by correction or baja.
- Existencias: add only, until operations exist. Correct and remove are absent, not disabled.

Write states: in flight (busy, navigation refused); done new (re-read); done reused (says already recorded, claim only); refused (draft kept); incomplete (alert glyph, verdict and what to fill in); claim conflict (own treatment, names the existing claim, offers correct dotacion); failed (nothing saved: `unavailable`, `not_signed_in`, `not_admitted`, `invalid`, `too_large`); unknown or `saved_unread` (held, never resent, writes wait behind `WriteHold`, banner offers the re-read). Landings: `saved`, `not_saved`, `repeatable`, `untold` and `null`, the last two staying held. Create checks the list for the minted id, correct the revision number, describe the descriptor sequence, claim the plan's claims, baja the list's baja state. The rule at `FE/components/ledger/setup/AssetsPane.tsx:104` that any refusal means `not_saved` is not carried over.

### Inventory operation classes

`ledger.inventory.list` as Write at `admitted.rs:99` matches its contract: the family's update capability set (`src/cadrumo/application/inventory/registered_operation.py:113`) yields `may_write`, pinned by `admitted.rs:201`. It over-declares upstream, since the executor only emits `NONE` (`src/cadrumo/application/inventory/registered_executor.py:198`), so a lost list answer can read as unknown. `valuation.preview` is the real desktop defect: it can record events (`src/cadrumo/application/operations/access_facts.py:202`) yet `FE/components/ledger/setup/InventoryPane.tsx:322` sends it as a read. S06 runs it as a held write with a `repeatable` landing. `InventoryPane.tsx:50` also hardcodes valuation methods and movement kinds, and those need a backend source.

### Agreed backend inputs

CADRUMO-AMORTIZATION2 accepted these for S12 on 2026-10-30, unbuilt at that time: event sequence and nullable recorded time; typed absence per row; `claimable` intervals; `used_by`; `matches_current_schedule` and typed stale reason; authored or projected edition; refusal sub-reason keys; an acquisition candidates read with unknown distinct from zero; an opaque window-minted asset id never shown to a person; a fixed backend `creating_operation`; `supersedes_claim_id`; atomic correction with superseding claims. The handoff's Modelo 130 row becomes an amount plus typed contributions, so the claim-count column goes. Earlier-year claiming is allowed for rate-based methods within that year's maximum and refused with a typed reason for methods depending on pending value and for free depreciation not taken.

Baja, per `2026-10-30-assets-core-disposal-adr` (accepted, S11 unimplemented, operation names draft): the date entered is the last day of service. A baja is a superseding revision carrying the disposal record, so the timeline shows it as that revision's event, and calculation results are derived, not events. The correction form never offers `out_of_service_date`. It is reversible through a further correcting revision, but effective claims crossing the boundary are superseded in the same write and are not restored by reversal, so the baja form must say so and the reversal must not imply it. Reason tokens are served by a contract, never hardcoded.
