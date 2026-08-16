---
generated: true
tags:
  - '#index'
  - '#profile-setup-flow'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:00802db3ee262b1e58761961300705961486c79c6842f12633b1bce630e20314'
related:
  - '[[2026-07-23-profile-setup-flow-W01-P01-S01]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S02]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S03]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S04]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S05]]'
  - '[[2026-07-23-profile-setup-flow-W01-P01-S06]]'
  - '[[2026-07-23-profile-setup-flow-W01-P02-S07]]'
  - '[[2026-07-23-profile-setup-flow-W01-P02-S08]]'
  - '[[2026-07-23-profile-setup-flow-W01-P02-S09]]'
  - '[[2026-07-23-profile-setup-flow-W01-P03-S10]]'
  - '[[2026-07-23-profile-setup-flow-W01-P03-S11]]'
  - '[[2026-07-23-profile-setup-flow-W01-P03-S12]]'
  - '[[2026-07-23-profile-setup-flow-W02-P04-S13]]'
  - '[[2026-07-23-profile-setup-flow-W02-P04-S14]]'
  - '[[2026-07-23-profile-setup-flow-W02-P04-S15]]'
  - '[[2026-07-23-profile-setup-flow-W03-P05-S16]]'
  - '[[2026-07-23-profile-setup-flow-W03-P05-S17]]'
  - '[[2026-07-23-profile-setup-flow-W03-P05-S18]]'
  - '[[2026-07-23-profile-setup-flow-W03-P05-S19]]'
  - '[[2026-07-23-profile-setup-flow-W03-P06-S20]]'
  - '[[2026-07-23-profile-setup-flow-W03-P06-S21]]'
  - '[[2026-07-23-profile-setup-flow-W03-P06-S22]]'
  - '[[2026-07-23-profile-setup-flow-W03-P07-S23]]'
  - '[[2026-07-23-profile-setup-flow-W03-P07-S24]]'
  - '[[2026-07-23-profile-setup-flow-W03-P07-S25]]'
  - '[[2026-07-23-profile-setup-flow-W03-P07-S34]]'
  - '[[2026-07-23-profile-setup-flow-W03-P07-S35]]'
  - '[[2026-07-23-profile-setup-flow-W03-P07-S36]]'
  - '[[2026-07-23-profile-setup-flow-W03-P08-S26]]'
  - '[[2026-07-23-profile-setup-flow-W03-P08-S27]]'
  - '[[2026-07-23-profile-setup-flow-W03-P08-S28]]'
  - '[[2026-07-23-profile-setup-flow-W04-P09-S29]]'
  - '[[2026-07-23-profile-setup-flow-W04-P09-S30]]'
  - '[[2026-07-23-profile-setup-flow-W04-P09-S31]]'
  - '[[2026-07-23-profile-setup-flow-W04-P09-S33]]'
  - '[[2026-07-23-profile-setup-flow-W04-P09-S37]]'
  - '[[2026-07-23-profile-setup-flow-adr]]'
  - '[[2026-07-23-profile-setup-flow-integration-shape-audit]]'
  - '[[2026-07-23-profile-setup-flow-page-catalogue-mapping-reference]]'
  - '[[2026-07-23-profile-setup-flow-plan]]'
  - '[[2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research]]'
  - '[[2026-07-24-profile-setup-flow-close-honesty-review-audit]]'
  - '[[2026-08-02-profile-setup-flow-tui-trigger-audit]]'
  - '[[2026-08-11-profile-setup-flow-critical-baseline-research]]'
---

# `profile-setup-flow` feature index

Auto-generated index of all documents tagged with `#profile-setup-flow`.

## Documents

### adr

- `2026-07-23-profile-setup-flow-adr` - `profile-setup-flow` adr: `paged profile setup flow with dynamic copy assembly and cotejo censal` | (**status:** `accepted`)

### audit

- `2026-07-23-profile-setup-flow-integration-shape-audit` - `profile-setup-flow` audit: `taxpayer profile integration shape and ADR grounding audit`
- `2026-07-24-profile-setup-flow-close-honesty-review-audit` - `profile-setup-flow` audit: `Close honesty review`
- `2026-08-02-profile-setup-flow-tui-trigger-audit` - `profile-setup-flow` audit: `profile create TUI trigger`

### exec

- `2026-07-23-profile-setup-flow-W01-P01-S01` - Reconcile the dual TaxpayerProfile derivation paths with a side-by-side read of load_active_taxpayer_profile versus taxpayer_profile_from_mapping, consolidating or documenting the layering before any commit-path wiring
- `2026-07-23-profile-setup-flow-W01-P01-S02` - Introduce the setup-incomplete lifecycle marker on the persisted profile record with schema and typed-model plumbing
- `2026-07-23-profile-setup-flow-W01-P01-S03` - Teach the lifecycle authority early-mint registration in setup-incomplete state, duplicate-tax-id refusal firing at mint, and discard-erase of an abandoned incomplete profile
- `2026-07-23-profile-setup-flow-W01-P01-S04` - Refuse modelo work on setup-incomplete profiles in the readiness gate with an instructive refusal naming the resume path
- `2026-07-23-profile-setup-flow-W01-P01-S05` - Surface setup-incomplete status in profile listings and the overview calendar
- `2026-07-23-profile-setup-flow-W01-P01-S06` - Delete CENSO_REFRESHED and reconcile every CENSO_APPLIED consumer per the retired-enum-member discipline
- `2026-07-23-profile-setup-flow-W01-P02-S07` - Build the profile-key to consuming-bindings legal-refs reverse index as a compiled-snapshot projection honoring the registry authority flow
- `2026-07-23-profile-setup-flow-W01-P02-S08` - Extend the Translatable-prefix validator into a reference-only copy gate that rejects literal copy strings at flow construction
- `2026-07-23-profile-setup-flow-W01-P02-S09` - Promote the profile-domain terminology concepts the pages will cite from draft to approved through the Handbook lifecycle
- `2026-07-23-profile-setup-flow-W01-P03-S10` - Pin the post-2025 M036 casilla ids and the official G313 certificate field list against primary sources, recording the addendum in the feature research
- `2026-07-23-profile-setup-flow-W01-P03-S11` - Implement the G313 certificate parser producing typed censal facts stamped with the artefact-origin non-official provenance token
- `2026-07-23-profile-setup-flow-W01-P03-S12` - Add the censal file --file ingestion sub-command routing parsed facts through the manual enrolment path
- `2026-07-23-profile-setup-flow-W02-P04-S13` - Re-sequence SETUP_FLOW sections into the eight-phase spine order with stable question ids, keeping both core registration slots fed and visible_when targets resolving to earlier questions
- `2026-07-23-profile-setup-flow-W02-P04-S14` - Run the locales scaffold and scaffold --check plus parity and honesty gates over the re-sequenced catalogue
- `2026-07-23-profile-setup-flow-W02-P04-S15` - Regenerate the api reference stubs and re-verify documented-command conformance after the re-sequence
- `2026-07-23-profile-setup-flow-W03-P05-S16` - Express the re-sequenced catalogue on the substrate FlowDefinition with copy-reference slots only, preserving the register_wizard_catalogue and register_project_answers feeds
- `2026-07-23-profile-setup-flow-W03-P05-S17` - Re-home the verify_setup_answers cross-field checks into flow-scope validators, enrolling section scope where a check's inputs are complete at phase exit
- `2026-07-23-profile-setup-flow-W03-P05-S18` - Bind the identity pages to the core.identity per-answer validators with per-IdentityDocument format-hint and failure copy references
- `2026-07-23-profile-setup-flow-W03-P05-S19` - Render the legal-provenance zone from schema legal_refs plus the reverse index with approved-concept references only
- `2026-07-23-profile-setup-flow-W03-P06-S20` - Implement the create-mode checkpoint port over incremental effective-dated facts with derived-cursor resume and lifecycle discard
- `2026-07-23-profile-setup-flow-W03-P06-S21` - Implement modify-mode FlowState staging with the atomic persist_patch diff commit and the declared per-mode no-op checkpoint
- `2026-07-23-profile-setup-flow-W03-P06-S22` - Surface modify-mode save-and-exit unavailability with an explicit message and a loud staged-edit discard on interruption
- `2026-07-23-profile-setup-flow-W03-P07-S23` - Add the descendant repeating group emitting the exact renta_family.descendiente fact shape and aggregates through descendant_facts_from_list, descendant NIFs validated by core.identity
- `2026-07-23-profile-setup-flow-W03-P07-S24` - Convert the descendiente and repair verbs into deep-link doors into the flow and delete their bespoke prompt loops in the same change
- `2026-07-23-profile-setup-flow-W03-P07-S25` - Convert the apoderado verb into a door that hosts the flow pages while routing writes to the ApoderadoService namespace, never profile facts
- `2026-07-23-profile-setup-flow-W03-P07-S34` - Migrate the non-interactive quiet and accept-defaults walks onto run_scripted_flow with one shared definition builder and one coercer, preserving force-visible law and localized refusal surfaces
- `2026-07-23-profile-setup-flow-W03-P07-S35` - Splice attach_descendant_group into the shared setup definition builder with the count page defaulting to zero descendants, pinning the group live on both frontends
- `2026-07-23-profile-setup-flow-W03-P07-S36` - Route interactive-edit descendant answers through the edit persist seam with count-shrink clearing, or gate the descendant group out of modify mode until that seam exists, closing the silent-no-op-on-write gap
- `2026-07-23-profile-setup-flow-W03-P08-S26` - Build the cotejo compare-select reconciliation of flow answers against the parsed G313 fact set with keep, adopt, and defer decisions
- `2026-07-23-profile-setup-flow-W03-P08-S27` - Persist deferred divergences as typed facts at commit and surface warning notices on later profile reads
- `2026-07-23-profile-setup-flow-W03-P08-S28` - Emit CENSO_APPLIED at cotejo artefact-apply and pin the emission site in the event contract test
- `2026-07-23-profile-setup-flow-W04-P09-S29` - Add roundtrip plus anti-tautology coverage for divergence facts, the setup-incomplete state, and resume projection
- `2026-07-23-profile-setup-flow-W04-P09-S30` - Verify the portable-export shape against the compatibility lifecycle for every schema addition
- `2026-07-23-profile-setup-flow-W04-P09-S31` - Author the user-facing setup-flow documentation through the documentation workflow with command conformance green
- `2026-07-23-profile-setup-flow-W04-P09-S37` - Add the AST gate asserting every tr(CONSTANT) call site's constant name carries the locale-key naming convention, closing the scanner-invisible-constant concealment class repo-wide
- `2026-07-23-profile-setup-flow-W04-P09-S33` - Run the fresh-context campaign-close honesty review and persist the close audit with every surfaced item tracked

### plan

- `2026-07-23-profile-setup-flow-plan` - `profile-setup-flow` plan

### reference

- `2026-07-23-profile-setup-flow-page-catalogue-mapping-reference` - `profile-setup-flow` reference: `page catalogue mapping`

### research

- `2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research` - `profile-setup-flow` research: `setup flow design hypothesis`
- `2026-08-11-profile-setup-flow-critical-baseline-research` - `profile-setup-flow` research: `Current profile manager information architecture and population pathways`
