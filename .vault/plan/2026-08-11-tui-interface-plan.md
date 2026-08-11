---
tags:
  - '#plan'
  - '#tui-interface'
date: '2026-08-11'
modified: '2026-08-11'
body_hash: 'sha256:72cb650fb7e46508774441f2ed6f4078135a9c66bd9680df2ba4a8d98eab51fe'
tier: L3
related:
  - '[[2026-08-11-tui-interface-adr]]'
  - '[[2026-08-11-tui-interface-research]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-11-tui-architecture-plan]]'
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-10-casilla-schema-plan]]'
---

<!-- RETIRED: P09, S26, S35 -->

# `tui-interface` plan

Deliver the task-led, progressively disclosed TUI application surface after its two prerequisite campaigns settle the canonical domain and platform contracts.

## Description

This L3 plan is intentionally blocked. The canonical modelo casilla schema campaign must finish first. The TUI architecture campaign must then finish against that landed schema, including its own explicit canonical Modelo-view migration, operation-owned `EphemeralSecretSubmission` capability, and closure of the legacy TUI tree. If those gaps are not present in the sibling campaign, its owners must amend and complete that campaign before its receipt is valid here. Only after both ordered commit receipts are recorded and verified may this plan add user-facing information architecture on top of the settled contracts. It does not build the operation platform, migrate packages, compose the root application, change packaging, alter any CLI module, add CLI-to-TUI coupling, delete legacy modules, or implement editable Modelo fields.

## Steps

## Wave `W01` - Post-dependency interface receipt

Verify casilla-schema closes first and TUI architecture subsequently closes against that output, then freeze the live public contracts this plan may consume. W01.P01 must close before W01.P02 or any later Phase or Wave begins.

### Phase `W01.P01` - Prerequisite campaign receipts

Record and validate committed close evidence proving casilla-schema closed first and TUI architecture subsequently closed against its landed contracts, including the upstream Modelo migration and secret-submission capability.

- [ ] `W01.P01.S01` - Record the casilla close receipt with S40 evidence and its commit identity; `.vault/reference/2026-08-11-tui-interface-dependency-receipt.md`.
- [ ] `W01.P01.S02` - Record the architecture close receipt with S103 evidence its commit identity and ancestry after the casilla receipt; `.vault/reference/2026-08-11-tui-interface-dependency-receipt.md`.
- [ ] `W01.P01.S03` - Validate the ordered dependency receipt public ModeloWorkReview canonical Modelo view zero legacy TUI and receipt-named secret-submission facade against the live tree; `src/cadrumo/entrypoints/tui/tests/test_dependency_receipts.py`.

### Phase `W01.P02` - Profile presentation contract

Freeze the application-owned profile projection required for requirement class, applicability, source, provenance, conflict, and readiness rendering.

- [ ] `W01.P02.S04` - Define typed profile presentation states for static requiredness conditional applicability filing preflight readiness relevance source provenance conflicts and explicit unknowns; `src/cadrumo/application/user_profile/_overview.py`.
- [ ] `W01.P02.S05` - Publish the settled profile presentation contract through the application facade; `src/cadrumo/application/user_profile/__init__.py`.
- [ ] `W01.P02.S06` - Prove the profile projection from real schema conditional-completeness filing-preflight selector and stored-fact inputs without presentation inference; `src/cadrumo/application/user_profile/tests/test_overview.py`.

## Wave `W02` - Reusable information-architecture components

Add presentation-only primitives and consistent status, error, and log behavior to the settled components package without taking application or operation authority.

### Phase `W02.P03` - Navigation and disclosure primitives

Provide reusable stage navigation, progressive disclosure, grouping, badges, and source-action presentation components.

- [ ] `W02.P03.S07` - Extend settled widgets with linear stage navigation disclosure groups requirement badges and source-action cards; `src/cadrumo/entrypoints/tui/components/widgets.py`.
- [ ] `W02.P03.S08` - Prove reusable navigation disclosure grouping focus and narrow-terminal behavior; `src/cadrumo/entrypoints/tui/components/tests/test_widgets.py`.

### Phase `W02.P04` - Status, error, and log presentation

Render already-classified status, safe errors, and bounded redacted logs without owning operation semantics.

- [ ] `W02.P04.S09` - Extend settled status error and log renderers for distinct advisories safe failures bounded history spinner and final outcomes; `src/cadrumo/entrypoints/tui/components`.
- [ ] `W02.P04.S10` - Prove render-only status error log and operation-feedback components consume public safe projections; `src/cadrumo/entrypoints/tui/components/tests/test_feedback.py`.

## Wave `W03` - Task-led profile experience

Build the five-stage profile journey on settled application projections, with explicit source actions, applicability, provenance, reconciliation, and readiness.

### Phase `W03.P05` - Five-stage profile shell

Compose Overview, Get data, Required, Review, and Ready as a linear journey whose inactive bodies are hidden.

- [ ] `W03.P05.S11` - Compose the five-stage profile journey with only the active stage body expanded; `src/cadrumo/entrypoints/tui/profile/app.py`.
- [ ] `W03.P05.S12` - Render overview required optional not-applicable and readiness summaries from the application projection; `src/cadrumo/entrypoints/tui/profile/status.py`.
- [ ] `W03.P05.S13` - Prove linear navigation progressive disclosure and stage completion without duplicating requirement policy; `src/cadrumo/entrypoints/tui/profile/tests/test_profile_journey.py`.

### Phase `W03.P06` - Profile acquisition and reconciliation views

Expose explicit source actions, provenance, conflicts, and exact apply or reject decisions through public application contracts.

- [ ] `W03.P06.S14` - Render explicit automatic-source capabilities scope authentication needs and operation launch actions; `src/cadrumo/entrypoints/tui/profile/overview.py`.
- [ ] `W03.P06.S15` - Render provenance current and proposed values conflicts and exact apply or reject reconciliation decisions; `src/cadrumo/entrypoints/tui/profile/sync_review.py`.
- [ ] `W03.P06.S16` - Prove acquisition is never implicit and reconciliation persists only accepted decisions through public contracts; `src/cadrumo/entrypoints/tui/profile/tests/test_sync_review.py`.

## Wave `W04` - Secret surfaces and generic flows

Complete the reusable login, registration, profile-picker, passphrase, and generic-flow experiences while keeping secret custody and flow semantics outside presentation code.

### Phase `W04.P07` - Authentication and secret management

Deliver profile selection, login, registration, password entry, profile-secret creation, and passphrase change as consumers of the receipt-named `EphemeralSecretSubmission` facade while preserving upstream secret custody.

- [ ] `W04.P07.S17` - Complete reusable masked credential and password-entry presentation over the receipt-named public EphemeralSecretSubmission facade; `src/cadrumo/entrypoints/tui/secret/credentials.py`.
- [ ] `W04.P07.S18` - Complete login and profile-picker presentation without moving authentication policy into the TUI; `src/cadrumo/entrypoints/tui/secret/login.py`.
- [ ] `W04.P07.S19` - Complete profile-secret creation and registration presentation through public application contracts; `src/cadrumo/entrypoints/tui/secret/registration.py`.
- [ ] `W04.P07.S20` - Complete passphrase-change presentation with confirmation outcome and cancellation states; `src/cadrumo/entrypoints/tui/secret/passphrase.py`.
- [ ] `W04.P07.S21` - Prove exact operation binding expiry single use mismatch refusal cancellation cleanup and canary non-retention through real secret journeys; `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`.

### Phase `W04.P08` - Generic guided flows

Rebuild reusable guided-flow presentation from settled application flow contracts without moving flow rules into the TUI.

- [ ] `W04.P08.S22` - Extend the settled guided-flow shell with reusable stage navigation validation summaries and cancellation; `src/cadrumo/entrypoints/tui/flows/app.py`.
- [ ] `W04.P08.S23` - Prove guided flows consume application-owned questions and decisions without embedding flow semantics; `src/cadrumo/entrypoints/tui/flows/tests/test_guided_flows.py`.

## Wave `W05` - Modelo review and navigation acceptance

Enhance the canonical read-only Modelo review surface and prove the prerequisite integration application exposes every interface destination without assigning app composition to this lane.

### Phase `W05.P10` - Read-only Modelo review

Render the landed canonical ModeloWorkReview, including representative structural outliers, without introducing editable casilla behavior.

- [ ] `W05.P10.S24` - Extend the landed Modelo review surface as a read-only consumer of ModeloWorkReview; `src/cadrumo/entrypoints/tui/modelo/view`.
- [ ] `W05.P10.S25` - Prove Modelo review grouping and applicability for M720 M200 2024 M100 2024 and 2025 and M349; `src/cadrumo/entrypoints/tui/modelo/tests/test_review_view.py`.

### Phase `W05.P11` - Application navigation acceptance

Prove the prerequisite integration application exposes profile secret flow operation and Modelo destinations without assigning composition work to this lane.

- [ ] `W05.P11.S27` - Prove the prerequisite integration app exposes every interface route through public facades and preserves in-progress task state; `src/cadrumo/entrypoints/tui/tests/test_application_navigation.py`.

## Wave `W06` - Responsive proof and closure

Prove the complete interface across terminal sizes, locales, themes, secret boundaries, and architecture gates before final review.

### Phase `W06.P12` - Responsive and localized behavior

Prove the complete task surface across supported terminal sizes, locales, and themes with visible progress and accessible focus behavior.

- [ ] `W06.P12.S28` - Prove every task surface at 80 by 24 120 by 36 and 160 by 48 terminal sizes; `src/cadrumo/entrypoints/tui/tests/test_responsive_surfaces.py`.
- [ ] `W06.P12.S29` - Prove all operator text and state labels render in English Spanish Catalan and Hungarian; `src/cadrumo/entrypoints/tui/tests/test_localized_surfaces.py`.
- [ ] `W06.P12.S30` - Prove light and dark themes preserve hierarchy focus visibility and non-color status meaning; `src/cadrumo/entrypoints/tui/tests/test_theme_accessibility.py`.

### Phase `W06.P13` - Architecture and security closure

Close import, secret-retention, ownership, and scope gates through focused real-behavior tests and independent review.

- [ ] `W06.P13.S31` - Enforce inbound-only imports and prohibit CLI application and domain modules from importing the TUI; `src/cadrumo/tests/test_import_hygiene_gate.py`.
- [ ] `W06.P13.S32` - Prove interface tests use production objects and contain no fake stub mock patch skip or xfail shortcuts; `src/cadrumo/entrypoints/tui/tests/test_test_integrity.py`.
- [ ] `W06.P13.S33` - Run the feature-scoped quality and VaultSpec gates for every changed interface path; `.vault/index/tui-interface.index.md`.
- [ ] `W06.P13.S34` - Record independent final architecture security usability and scope review before closing the campaign; `.vault/review/2026-08-11-tui-interface-review.md`.

## Parallelization

Waves are ordered. Nothing may run before W01 closes. Within later Waves, Phases may run in parallel only when their exact paths and public contracts do not overlap; joins remain serialized through public facades.

## Verification

Completion requires every Step to be closed, the two prerequisite campaign receipts to be proven in order, narrow and responsive real-behavior TUI tests to pass, import boundaries to remain clean, all four supported locales and both themes to render, secret canaries to prove non-retention, and a final architecture review to confirm that no CLI, operation-platform, package-migration, legacy-deletion, or Modelo-edit scope entered this campaign.
