---
tags:
  - '#plan'
  - '#tui-interface'
date: '2026-08-11'
tier: L3
related:
  - '[[2026-08-11-tui-interface-adr]]'
  - '[[2026-08-11-tui-interface-research]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-11-tui-architecture-plan]]'
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-10-casilla-schema-plan]]'
  - '[[2026-08-24-tui-registry-api-gate-adr]]'
  - '[[2026-08-24-tui-registry-api-gate-research]]'
  - '[[2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit]]'
  - '[[2026-08-24-modelo-edit-contract-adr]]'
  - '[[2026-08-24-tui-modelo-workspace-interface-adr]]'
  - '[[2026-08-24-tui-modelo-workspace-interface-research]]'
modified: '2026-08-26'
body_hash: 'sha256:6bd2e00c35541d9c4dd287c7fc5f8aead8d545a5cca294ef20f8a67d16fd886c'
---

<!-- RETIRED: P09, S26, S35 -->

# `tui-interface` plan

Deliver the task-led, progressively disclosed TUI surface through receipt-gated cohorts that consume canonical Modelo, Workspace, edit, operation, and platform contracts.

## Description

This L3 plan executes the accepted interface decision together with the accepted Workspace V1, ModeloEditContractV1, and Modelo workspace-interface decisions. W02-W04 preserve the existing profile, reusable component, secret, and guided-flow work. Modelo delivery is receipt-driven: W05.P10 is C1 bounded review; W05.P10a consumes the architecture-owned C2 dependency receipt; W05.P11 is C2 complex read; W06.P12a consumes the architecture-owned operation, financial-operand, and Edit Contract C3 dependency receipts; W06.P12b is the C3 memory-only editor; W06.P12c is C4 lifecycle actions; and W06.P12 plus W06.P13 close C5 accessibility and the final fixed point.

Cohort gates replace the former blanket architecture-close blockade. C1 waits for the accepted companion, accepted Casilla review, and architecture-owned migration-lane evidence. C2 waits for C1 and the Workspace receipt. C3 waits for the C0 operation observation exit, C2 exit, edit-contract receipt, and operation-owned financial-operand receipt. C4 waits for C3 plus each action's canonical capability and enrolled operation. C5 waits for C4 and the complete classified destination and action denominator. Operation observation, transient financial custody, root composition, launcher and packaging work, reverse migration, and legacy deletion remain in the architecture plan; this plan consumes their receipts and verifies installed composition. Workspace and edit application work delegates existing readiness, review, calculation, persistence, lifecycle, and operation authority and must not create a second producer, semantic join, capability owner, or mutation writer.

## Steps

## Wave `W01` - Receipt infrastructure and interface foundations

Establish exact current-HEAD receipt and generated action-denominator gates before any interface surface becomes callable, then freeze the profile projection. C1 may open after its bounded-review migration predecessor; later Modelo cohorts wait for their own receipts rather than a blanket architecture-plan close.

### Phase `W01.P01` - Receipt schemas, denominator, and C1 entrance

Create one exact receipt vocabulary and generated action denominator, then record the accepted bounded-review and migration-lane facts that alone admit C1.

- [x] `W01.P01.S01` - Record the C1 entrance receipt with the accepted companion stem, accepting commit and body hash, canonical Casilla review evidence, and architecture migration-lane commit ancestry; `.vault/reference/2026-08-11-tui-interface-dependency-receipt.md`.
- [x] `W01.P01.S02` - Implement only the strict current-HEAD Modelo Workspace C1-C5 interface exit receipt schemas and validators with exact predecessor digests, discriminated proofs, distinct compatibility axes, and delegated validation of architecture-owned incoming receipts; `dev/quality/modelo_workspace_receipts.py`.
- [x] `W01.P01.S03` - Prove every receipt validator rejects reordered or drifting predecessors, non-accepted authorities, unsupported compatibility axes, unclassified actions, and availability before its owning exit is green; `dev/tests/test_modelo_workspace_receipts.py`.
- [x] `W01.P01.S36` - Build ModeloWorkspaceActionDenominatorV1 from the canonical action catalogue, operation definitions, complete command graph and TuiCapability values, direct effect sites, routes, action views, dispatch rows, and typed exclusions; `dev/quality/modelo_workspace_action_denominator.py`.
- [x] `W01.P01.S37` - Generate the current-HEAD action-denominator artifact with every C1 direct query classified, modelo.work.create DEFERRED under work-lifecycle ownership, modelo.work.amend a distinct future C4 mutation, and modelo.work.amend_wizard FLOW_OWNED pending C4 disposition; `.vault/reference/2026-08-24-tui-modelo-workspace-action-denominator.md`.

### Phase `W01.P02` - Profile presentation contract

Freeze the application-owned profile projection required for requirement class, applicability, source, provenance, conflict, and readiness rendering.

- [x] `W01.P02.S04` - Define typed profile presentation states for static requiredness conditional applicability filing preflight readiness relevance source provenance conflicts and explicit unknowns; `src/cadrumo/application/user_profile/presentation.py`.
- [x] `W01.P02.S05` - Publish the settled profile presentation contract through the application facade; `src/cadrumo/application/user_profile/presentation.py public defining module`.
- [x] `W01.P02.S06` - Prove the profile projection from real schema conditional-completeness filing-preflight selector and stored-fact inputs without presentation inference; `src/cadrumo/application/user_profile/tests/test_presentation.py`.
- [x] `W01.P02.S94` - Complete conditional-applicability assessment in the profile presentation contract for the cases W01.P02.S04 left classified as OPTIONAL rather than assessed: the multi-field IVA-regime trigger resolved through modelo_iva_profile_required_paths, and every repeatable section, so a field is reported not_applicable or applicable_required_missing on its real trigger instead of defaulting to optional; `src/cadrumo/application/user_profile/presentation.py and src/cadrumo/application/user_profile/tests/test_presentation.py`.

## Wave `W02` - Reusable information-architecture components

Add presentation-only primitives and consistent status, error, and log behavior to the settled components package without taking application or operation authority.

### Phase `W02.P03` - Navigation and disclosure primitives

Provide reusable stage navigation, progressive disclosure, grouping, badges, and source-action presentation components.

- [x] `W02.P03.S07` - Extend settled widgets with linear stage navigation disclosure groups requirement badges and source-action cards; `src/cadrumo/entrypoints/tui/components/widgets.py`.
- [x] `W02.P03.S08` - Prove reusable navigation disclosure grouping focus and narrow-terminal behavior; `src/cadrumo/entrypoints/tui/components/tests/test_widgets.py`.

### Phase `W02.P04` - Status, error, and log presentation

Render already-classified status, safe errors, and bounded redacted logs without owning operation semantics.

- [x] `W02.P04.S09` - Extend settled status error and log renderers for distinct advisories safe failures bounded history spinner and final outcomes; `src/cadrumo/entrypoints/tui/components`.
- [x] `W02.P04.S10` - Prove render-only status error log and operation-feedback components consume public safe projections; `src/cadrumo/entrypoints/tui/components/tests/test_feedback.py`.

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

## Wave `W05` - Modelo C1-C2 read cohorts

Open the bounded review and complex read workspace sequentially: C1 consumes the migrated canonical ModeloWorkReview; Workspace V1 and its C2 dependency receipt then open only baseline-consistent bounded read destinations. No edit or operation backend is implemented in this Wave.

### Phase `W05.P10` - C1 bounded review destination

Register the one bounded review destination over the relocated canonical ModeloWorkReview renderer and close C1 only after its accessibility and current-HEAD receipt proofs pass.

- [x] `W05.P10.S24` - Register modelo.work.select and the sole C1 modelo.work.review destination over the architecture-relocated view, consuming the exact public ModeloWorkReview without a second producer or legacy route; `src/cadrumo/entrypoints/tui/modelo/view`.
- [x] `W05.P10.S25` - Prove C1 review outliers, stable keyboard order, non-colour status, and all four locales, three geometries, and two themes before its route can become callable; `src/cadrumo/entrypoints/tui/modelo/tests/test_c1_bounded_review.py`.
- [x] `W05.P10.S38` - Emit and validate ModeloWorkspaceC1ExitReceiptV1 with the accepted-companion prefix, migration evidence, denominator digest, C1 accessibility matrix, production route, and availability fence; `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c1-exit-receipt.md`.

### Phase `W05.P10a` - Workspace C2 dependency handoff

Consume the architecture-owned Workspace V1 receipt and independently verify its current-HEAD identity before any complex TUI route imports the public facade. This phase never implements or revalidates the application contract itself.

- [ ] `W05.P10a.S49` - Verify and pin the exact green ModeloWorkspaceC2DependencyReceiptV1, its C1 predecessor, accepted authorities, schema fingerprint, producer and field inventories, conformance digest, current source ancestry, and declared C2 routes; `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`.

### Phase `W05.P11` - C2 complex read destinations

Atomically replace the C1 detail route with the closed Workspace destination catalogue, map Workspace V1 into TUI-local read state, and prove bounded baseline-consistent rendering before C2 availability.

- [ ] `W05.P11.S27` - Atomically replace the C1 review selection outcome with modelo.workspace.overview, register the closed destination and route-factory census, and prove zero remaining modelo.work.review routes or aliases; `src/cadrumo/entrypoints/tui/modelo/routes.py`.
- [ ] `W05.P11.S50` - Define frozen callback-free Workspace chrome, destination, section, scalar, repeated-row, provenance, capability, refusal, validation, and action view models keyed only by semantic identity; `src/cadrumo/entrypoints/tui/modelo/view/models.py`.
- [ ] `W05.P11.S51` - Implement ModeloWorkspaceReadSession and the read controller with exact version admission, baseline-pinned facet traversal, bounded paging, locale-only refresh proof, and whole-session stale invalidation; `src/cadrumo/entrypoints/tui/modelo/view/controller.py`.
- [ ] `W05.P11.S52` - Render modelo.workspace.overview with natural and exact address disclosure, revision timeline, status, capability summary, refusals, safe actions, and collapsible narrow-terminal chrome; `src/cadrumo/entrypoints/tui/modelo/view/overview.py`.
- [ ] `W05.P11.S53` - Render modelo.workspace.inputs from bounded section, scalar, and repeated-row facets with stable keys and explicit edit dispositions but no edit control before C3; `src/cadrumo/entrypoints/tui/modelo/view/inputs.py`.
- [ ] `W05.P11.S54` - Render modelo.workspace.results for the current Workspace session and an explicitly selected read-only ModeloRevisionPick without mixing historical and current capability; `src/cadrumo/entrypoints/tui/modelo/view/results.py`.
- [ ] `W05.P11.S55` - Render modelo.workspace.provenance through bounded lazy causal expansion with producer-supplied cycle and depth dispositions and no locally synthesized edges; `src/cadrumo/entrypoints/tui/modelo/view/provenance.py`.
- [ ] `W05.P11.S56` - Render modelo.workspace.verification from canonical findings, readiness axes, capability dispositions, evidence, and recovery actions without deriving a second readiness verdict; `src/cadrumo/entrypoints/tui/modelo/view/verification.py`.
- [ ] `W05.P11.S57` - Render modelo.workspace.filing from canonical filing state, history, export capability, evidence-backed refusals, and human-handoff facts without remote AEAT submission; `src/cadrumo/entrypoints/tui/modelo/view/filing.py`.
- [ ] `W05.P11.S58` - Prove C2 route replacement, destination and factory census, projection-kind coverage, large and deep schemas, empty and paged rows, overflow, provenance, refusals, capabilities, keyboard focus, all locales, geometries, and themes before availability; `src/cadrumo/entrypoints/tui/modelo/tests/test_c2_workspace_accessibility.py`.
- [ ] `W05.P11.S59` - Emit and validate ModeloWorkspaceC2ExitReceiptV1 with C1 and Workspace dependency digests, exact read compatibility coordinates, destination and denominator digests, scale and accessibility matrix, production composition, and availability fence; `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c2-exit-receipt.md`.

## Wave `W06` - Modelo C3-C5 editor, lifecycle actions, and closure

After C0, C2, edit-contract, and financial-operand receipts are green, build the memory-only editor, independently gate lifecycle actions, and close the complete interface fixed point. Operation observation, transient custody, root composition, packaging, and migration remain owned by the architecture plan.

### Phase `W06.P12a` - C3 application dependency handoff

Consume the architecture-owned C0, Workspace C2, Edit Contract, and transient-financial-operand receipts and independently pin their exact compatibility tuple before mounting an editor. This phase never declares DTOs, parsing, persistence, custody, or mutation services.

- [ ] `W06.P12a.S71` - Verify and pin the exact green operation observation, Workspace C2, ModeloEditContractC3DependencyReceiptV1, and financial-operand receipts, including accepted authorities, predecessor digests, distinct schema/version axes, atomicity and non-retention proofs, current source ancestry, and the declared C3 destinations; `.vault/reference/2026-08-24-modelo-edit-contract-c3-dependency-receipt.md`.

### Phase `W06.P12b` - C3 memory-only editor

Map the admitted edit contract into TUI-local scalar and row state, review-only submission, stale conflict, and typed post-operation refresh without retaining financial values outside permitted memory.

- [ ] `W06.P12b.S72` - Define the memory-only ModeloEditSession and DraftRowId state machine with separate read and edit baselines, semantic dirty addresses, canonical typed staged values, ordered row intents, validation, and explicit abandon; `src/cadrumo/entrypoints/tui/modelo/edit/session.py`.
- [ ] `W06.P12b.S73` - Render scalar controls only from the admitted permitted surface, delegate every lexeme to ModeloEditParseRequestV1, preserve zero, false, clear, override removal, and unchanged distinctions, and block review on an unresolved locale-tagged lexeme; `src/cadrumo/entrypoints/tui/modelo/edit/fields.py`.
- [ ] `W06.P12b.S74` - Render stable-key repeated rows with whole-row add, update, delete, and explicitly permitted move behavior, never using widget position as identity or submitting an incomplete draft row; `src/cadrumo/entrypoints/tui/modelo/edit/rows.py`.
- [ ] `W06.P12b.S75` - Build the mandatory modelo.edit.review transaction gate with every changed semantic address, scalar and row intent, addressable validation, focus return, unsaved-change stay or abandon choice, and no fabricated supervisor approval; `src/cadrumo/entrypoints/tui/modelo/edit/review.py`.
- [ ] `W06.P12b.S76` - Admit editor routes only after the complete ModeloEditCompatibilityTupleV1 matches the pinned Workspace, definition manifest and digests, observation, REVIEW, refresh-target, and financial-operand schema coordinates before any lexeme is accepted; `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`.
- [ ] `W06.P12b.S77` - Submit only normalized ModeloEditSubmissionV1 through the public operation-owned financial handoff, fold public observation to settlement, resolve only the typed Workspace refresh target, and enter stale conflict without merge, rebase, result-ref interpretation, or old-view patching; `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`.
- [ ] `W06.P12b.S78` - Prove C3 lexical-error focus, scalar distinctions, row editing, review and abandon, exact tuple refusal, stale conflict, locale switch, operation handoff, terminal refresh, all accessibility axes, and unique-sentinel non-retention before editor availability; `src/cadrumo/entrypoints/tui/modelo/tests/test_c3_editor_accessibility.py`.
- [ ] `W06.P12b.S79` - Emit and validate ModeloWorkspaceC3ExitReceiptV1 against C0, C2, edit-contract, and financial-operand predecessor digests, the exact compatibility tuple, editor state and row proofs, accessibility matrix, refresh behavior, non-retention, denominator, and availability fence; `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c3-exit-receipt.md`.

### Phase `W06.P12c` - C4 lifecycle actions and action fixed point

Project each lifecycle action independently through canonical capability and operation owners, reconcile create and amendment classifications, and require action-specific accessibility and refresh proof before availability.

- [ ] `W06.P12c.S80` - Define callback-free ModeloActionView rows and one closed controller dispatch map over public query, capability, edit, and operation ports with exact result destinations and no direct executor or writer calls; `src/cadrumo/entrypoints/tui/modelo/actions.py`.
- [ ] `W06.P12c.S81` - Regenerate the complete action denominator and fail missing, duplicate, stale, or unclassified action-catalogue, operation, command-graph, effect-site, route, view, dispatch, flow-owned, deferred, and non-visual candidates; `dev/quality/modelo_workspace_action_denominator.py`.
- [ ] `W06.P12c.S82` - Enroll rename only through its canonical lifecycle capability and registered operation, and prove available, refused, terminal effect, typed refresh, focus return, and every supported geometry independently; `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_rename_action.py`.
- [ ] `W06.P12c.S83` - Enroll discard only through its canonical destructive lifecycle capability, exact approval interaction, and registered operation, and prove refusal, cancellation, effect, refresh, focus return, and every supported geometry independently; `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_discard_action.py`.
- [ ] `W06.P12c.S84` - Enroll verify only through its canonical validation capability and registered operation, and prove refused and unmeasured states, findings, terminal effect, typed refresh, focus return, and every supported geometry independently; `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_verify_action.py`.
- [ ] `W06.P12c.S85` - Enroll file only through its canonical local filing and human-handoff capability and registered operation, and prove no remote AEAT submission, refusal, interaction, terminal effect, typed refresh, focus return, and every supported geometry independently; `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_file_action.py`.
- [ ] `W06.P12c.S86` - Enroll export only through its canonical export-readiness capability and registered operation, and prove evidence-backed refusal, interaction, terminal effect, typed refresh, focus return, and every supported geometry independently; `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_export_action.py`.
- [ ] `W06.P12c.S87` - Enroll modelo.work.amend as a distinct C4 amendment mode and atomically replace the amend-wizard TUI capability or classify that transitional row DEFERRED with owner, evidence, and reopening gate; `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_amend_action.py`.
- [ ] `W06.P12c.S88` - Keep modelo.work.create visibly DEFERRED under the existing work-lifecycle owner with absent-work admission, operation, atomic write-set, result-receipt, dependency, and interface reopening conditions, and prove C1-C5 cannot invoke it; `src/cadrumo/entrypoints/tui/modelo/tests/test_create_deferred.py`.
- [ ] `W06.P12c.S89` - Prove every C4 candidate has a visible capability disposition, exact registered definition when mutating, declared interaction, terminal refresh mapping, action-specific locale and accessibility matrix, and no availability before its own proof is green; `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_action_accessibility.py`.
- [ ] `W06.P12c.S90` - Emit and validate ModeloWorkspaceC4ExitReceiptV1 with the C3 predecessor, zero unclassified candidates, independently green rename, discard, verify, file, export, and amend rows, create deferral, amend-wizard disposition, denominator digest, and availability fence; `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c4-exit-receipt.md`.

### Phase `W06.P12` - C5 aggregate accessibility matrix

Re-run the complete C1-C4 interface across every required geometry, locale, theme, keyboard path, non-colour state, scale fixture, refusal, and conflict before final availability.

- [ ] `W06.P12.S28` - Exercise every C1-C4 destination and action at 80x24, 120x36, and 160x48 with bounded mounts, long labels, deep sections, paged rows, refusals, and conflicts; `src/cadrumo/entrypoints/tui/tests/test_responsive_surfaces.py`.
- [ ] `W06.P12.S29` - Prove English, Spanish, Catalan, and Hungarian change only display fields while semantic address, capability, edit intent, focus identity, and receipt coordinates remain stable; `src/cadrumo/entrypoints/tui/tests/test_localized_surfaces.py`.
- [ ] `W06.P12.S30` - Prove light and dark themes preserve hierarchy, keyboard focus, textual status, dirty and validation meaning, and every non-colour interaction state; `src/cadrumo/entrypoints/tui/tests/test_theme_accessibility.py`.

### Phase `W06.P13` - C5 fixed-point and security closure

Close import, producer, writer, route, action, receipt, installed-composition, non-retention, and real-behavior gates against the live tree and current generated denominators.

- [ ] `W06.P13.S31` - Enforce inbound-only TUI imports and reject private registry, repository, CLI, operation-persistence, duplicate Workspace or review producer, and duplicate mutation-writer reaches; `src/cadrumo/tests/test_import_hygiene_gate.py`.
- [ ] `W06.P13.S32` - Prove C1-C5 interface tests use production objects and real behavior with no fake, stub, mock, patch, skip, xfail, or sensitive golden-payload shortcut; `src/cadrumo/entrypoints/tui/tests/test_test_integrity.py`.
- [ ] `W06.P13.S33` - Run feature-scoped quality, plan, VaultSpec, receipt-validator, action-denominator, and installed-composition gates for every changed interface and application.modelo path; `.vault/index/tui-interface.index.md`.
- [ ] `W06.P13.S34` - Record independent final architecture, security, accessibility, redeclaration, and scope review after the green C5 receipt; `.vault/audit/2026-08-11-tui-interface-audit.md`.
- [ ] `W06.P13.S91` - Prove the final current-HEAD producer, writer, route, destination, action, command-capability, denominator, and receipt fixed point has zero duplicate authorities, aliases, unclassified candidates, stale exclusions, or transitional TUI rows; `dev/tests/test_modelo_workspace_fixed_point.py`.
- [ ] `W06.P13.S92` - Prove the architecture-owned installed root application composes exactly the green C1-C4 route and action factories, keeps every non-green surface uncallable, preserves in-progress semantic focus, and exposes no CLI-to-TUI import; `src/cadrumo/entrypoints/tui/tests/test_installed_modelo_workspace.py`.
- [ ] `W06.P13.S93` - Emit and validate ModeloWorkspaceC5ExitReceiptV1 with the C4 predecessor, aggregate accessibility and scale matrix, exact compatibility coordinates, route and action anti-vacuity, no-transitional-TUI, non-retention, canonical-owner census, and installed-composition proof; `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c5-exit-receipt.md`.

## Parallelization

W01 receipt infrastructure and the generated denominator run first. W02-W04 may then proceed over whichever architecture-owned public seams already have green receipts; those Waves do not waive any Modelo cohort gate. Within W05, C1 closes before Workspace V1 mints the C2 dependency receipt, and C2 closes only after both predecessors validate on current HEAD.

W06.P12a performs only the dependency handoff after the architecture-owned C0, Workspace C2, edit-contract, and financial-protocol receipts are green. W06.P12b starts only after those receipts and the C2 interface exit validate. W06.P12c starts after C3; individual lifecycle action proofs may run in parallel only when their exact contracts and paths do not overlap, then join in the C4 receipt. C5 aggregate accessibility and fixed-point closure remain serialized after C4. Architecture-owned root composition stays in its sibling lane; this plan consumes its commit and receipt evidence rather than reimplementing it.

## Verification

Completion requires every Step and execution record to close and every C1-C5 entrance and exit validator to pass against current HEAD with its exact ordered predecessor paths, schemas, commits, content digests, decision body hashes, compatibility coordinates, and availability fence. The generated action denominator must have no missing, duplicate, stale, or unclassified candidate; create remains explicitly DEFERRED, amendment has one C4 disposition, and no transitional TUI row remains at C5.

The exact Workspace, edit, public-definition manifest and contract-set, enrolled definition and payload schema, observation, REVIEW, refresh-target, and transient-financial version axes must be independently pinned and unsupported tuples refused before mounting a dependent route or accepting a lexeme. Canonical-owner checks must prove one review producer, one Workspace semantic join, one readiness and capability authority per fact, one calculation revision writer, one lifecycle authority, and no redeclared public DTO or parser. Each cohort's locale, geometry, theme, keyboard, non-colour, scale, refusal, conflict, focus, and production-route proof must be green before availability. Final gates also require real production behavior, inbound-only imports, sensitive sentinel non-retention, no private registry or CLI reach, an installed architecture-owned root containing only green routes and actions, and no duplicated operation, custody, packaging, migration, or deletion ownership.
