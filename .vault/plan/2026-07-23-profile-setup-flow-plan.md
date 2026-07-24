---
tags:
  - '#plan'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-24'
tier: L3
related:
  - '[[2026-07-23-profile-setup-flow-adr]]'
  - '[[2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research]]'
  - '[[2026-07-23-profile-setup-flow-integration-shape-audit]]'
---

<!-- RETIRED: S32 -->

# `profile-setup-flow` plan

## Wave `W01` - Substrate-independent foundations

Land every flow deliverable that does not depend on the tui-wizard-substrate FlowEngine: the setup-incomplete lifecycle state and early-mint groundwork, CENSO event reconciliation, the legal-refs reverse index and copy-reference gates, the G313 artefact parser, and the derivation-path reconciliation the ADR hands to plan scope.

### Phase `W01.P01` - Lifecycle state and event reconciliation

Introduce the setup-incomplete profile lifecycle state with early-mint groundwork, make every consumer recognize it, reconcile the dormant CENSO event members, and close the dual TaxpayerProfile derivation-path question.

- [x] `W01.P01.S01` - Reconcile the dual TaxpayerProfile derivation paths with a side-by-side read of load_active_taxpayer_profile versus taxpayer_profile_from_mapping, consolidating or documenting the layering before any commit-path wiring; `src/cadrumo/domain/deadlines/_profiles.py`.
- [x] `W01.P01.S02` - Introduce the setup-incomplete lifecycle marker on the persisted profile record with schema and typed-model plumbing; `src/cadrumo/domain/user_profile/`.
- [x] `W01.P01.S03` - Teach the lifecycle authority early-mint registration in setup-incomplete state, duplicate-tax-id refusal firing at mint, and discard-erase of an abandoned incomplete profile; `src/cadrumo/application/user_profile/_lifecycle.py`.
- [x] `W01.P01.S04` - Refuse modelo work on setup-incomplete profiles in the readiness gate with an instructive refusal naming the resume path; `src/cadrumo/application/modelo/_profile_readiness_gate.py`.
- [x] `W01.P01.S05` - Surface setup-incomplete status in profile listings and the overview calendar; `src/cadrumo/entrypoints/cli/_config/`.
- [x] `W01.P01.S06` - Delete CENSO_REFRESHED and reconcile every CENSO_APPLIED consumer per the retired-enum-member discipline; `src/cadrumo/domain/buckets/_event.py`.

### Phase `W01.P02` - Grounding data projections and gates

Build the profile-key to legal-refs reverse index from the compiled registry snapshot, the reference-only copy gate, and promote the profile-domain terminology concepts the pages will cite.

- [x] `W01.P02.S07` - Build the profile-key to consuming-bindings legal-refs reverse index as a compiled-snapshot projection honoring the registry authority flow; `src/cadrumo/domain/calculations/registry/`.
- [x] `W01.P02.S08` - Extend the Translatable-prefix validator into a reference-only copy gate that rejects literal copy strings at flow construction; `src/cadrumo/application/wizard/_models.py`.
- [x] `W01.P02.S09` - Promote the profile-domain terminology concepts the pages will cite from draft to approved through the Handbook lifecycle; `src/cadrumo/_data/terminology/concepts/`.

### Phase `W01.P03` - G313 censal artefact ingestion

Primary-source the M036 and G313 field reality, then build the certificate parser and the file --file ingestion surface producing non-official-tier censal facts through the manual enrolment path.

- [x] `W01.P03.S10` - Pin the post-2025 M036 casilla ids and the official G313 certificate field list against primary sources, recording the addendum in the feature research; `.vault/research/2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research.md`.
- [x] `W01.P03.S11` - Implement the G313 certificate parser producing typed censal facts stamped with the artefact-origin non-official provenance token; `src/cadrumo/adapters/inbound/`.
- [x] `W01.P03.S12` - Add the censal file --file ingestion sub-command routing parsed facts through the manual enrolment path; `src/cadrumo/entrypoints/cli/_config/`.

## Wave `W02` - Catalogue re-sequencing on the current runner

Re-sequence the eleven catalogue sections into the eight-phase spine order with ids and profile keys stable, running on the existing forward-only runner so operators get the corrected order before the substrate lands; sweep locales and conformance gates.

### Phase `W02.P04` - Spine re-sequence and sweep

Reorder the catalogue sections into the eight-phase spine with stable ids, keep both core registration slots fed, and sweep locales, docs, and conformance gates.

- [x] `W02.P04.S13` - Re-sequence SETUP_FLOW sections into the eight-phase spine order with stable question ids, keeping both core registration slots fed and visible_when targets resolving to earlier questions; `src/cadrumo/application/wizard/_catalogue.py`.
- [x] `W02.P04.S14` - Run the locales scaffold and scaffold --check plus parity and honesty gates over the re-sequenced catalogue; `src/cadrumo/locales/`.
- [x] `W02.P04.S15` - Regenerate the api reference stubs and re-verify documented-command conformance after the re-sequence; `docs/api/`.

## Wave `W03` - Substrate integration

Express the catalogue on the FlowDefinition contract once the tui-wizard-substrate engine lands: paged copy assembly, validator re-homing, create and modify persistence modes, descendant repeating group, satellite deep-links, and the cotejo censal phase.

### Phase `W03.P05` - FlowDefinition expression and validators

Express the re-sequenced catalogue on the substrate FlowDefinition with copy references only, re-home the verifier checks into flow-scope validators, and bind identity pages to core.identity.

- [x] `W03.P05.S16` - Express the re-sequenced catalogue on the substrate FlowDefinition with copy-reference slots only, preserving the register_wizard_catalogue and register_project_answers feeds; `src/cadrumo/application/wizard/`.
- [x] `W03.P05.S17` - Re-home the verify_setup_answers cross-field checks into flow-scope validators, enrolling section scope where a check's inputs are complete at phase exit; `src/cadrumo/application/wizard/_verifier.py`.
- [x] `W03.P05.S18` - Bind the identity pages to the core.identity per-answer validators with per-IdentityDocument format-hint and failure copy references; `src/cadrumo/application/wizard/`.
- [x] `W03.P05.S19` - Render the legal-provenance zone from schema legal_refs plus the reverse index with approved-concept references only; `src/cadrumo/application/wizard/`.

### Phase `W03.P06` - Create and modify persistence modes

Implement facts-as-checkpoint create (early mint, incremental facts, derived resume, discard) and staged atomic modify (FlowState staging, persist_patch diff commit, loud no-resume honesty surfaces).

- [x] `W03.P06.S20` - Implement the create-mode checkpoint port over incremental effective-dated facts with derived-cursor resume and lifecycle discard; `src/cadrumo/application/wizard/_persistence.py`.
- [x] `W03.P06.S21` - Implement modify-mode FlowState staging with the atomic persist_patch diff commit and the declared per-mode no-op checkpoint; `src/cadrumo/application/wizard/_commands.py`.
- [x] `W03.P06.S22` - Surface modify-mode save-and-exit unavailability with an explicit message and a loud staged-edit discard on interruption; `src/cadrumo/application/wizard/_commands.py`.

### Phase `W03.P07` - Descendants and satellite doors

Land the net-new descendant repeating group emitting the exact established fact shape, and convert descendiente, apoderado, and repair into deep-link doors while deleting their bespoke loops.

- [x] `W03.P07.S23` - Add the descendant repeating group emitting the exact renta_family.descendiente fact shape and aggregates through descendant_facts_from_list, descendant NIFs validated by core.identity; `src/cadrumo/application/wizard/_catalogue.py`.
- [x] `W03.P07.S24` - Convert the descendiente and repair verbs into deep-link doors into the flow and delete their bespoke prompt loops in the same change; `src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [x] `W03.P07.S25` - Convert the apoderado verb into a door that hosts the flow pages while routing writes to the ApoderadoService namespace, never profile facts; `src/cadrumo/entrypoints/cli/_config/_apoderado.py`.
- [x] `W03.P07.S34` - Migrate the non-interactive quiet and accept-defaults walks onto run_scripted_flow with one shared definition builder and one coercer, preserving force-visible law and localized refusal surfaces; `src/cadrumo/application/wizard/_commands.py`.
- [x] `W03.P07.S35` - Splice attach_descendant_group into the shared setup definition builder with the count page defaulting to zero descendants, pinning the group live on both frontends; `src/cadrumo/application/wizard/_commands.py`.
- [x] `W03.P07.S36` - Route interactive-edit descendant answers through the edit persist seam with count-shrink clearing, or gate the descendant group out of modify mode until that seam exists, closing the silent-no-op-on-write gap; `src/cadrumo/application/wizard/_persistence.py`.

### Phase `W03.P08` - Cotejo censal phase

Wire the compare-select reconciliation of flow answers against the parsed G313 fact set with defer-as-divergence, notices, and the reconciled CENSO_APPLIED emission.

- [x] `W03.P08.S26` - Build the cotejo compare-select reconciliation of flow answers against the parsed G313 fact set with keep, adopt, and defer decisions; `src/cadrumo/application/wizard/`.
- [x] `W03.P08.S27` - Persist deferred divergences as typed facts at commit and surface warning notices on later profile reads; `src/cadrumo/application/user_profile/`.
- [x] `W03.P08.S28` - Emit CENSO_APPLIED at cotejo artefact-apply and pin the emission site in the event contract test; `src/cadrumo/application/user_profile/`.

## Wave `W04` - Hardening and close

Roundtrip and parity coverage for every new persistence surface, documentation and conformance sweeps, and the campaign-close honesty review.

### Phase `W04.P09` - Roundtrips, docs, and honesty close

Roundtrip and anti-tautology coverage for the new persistence surfaces, parity and conformance sweeps, user documentation, and the fresh-context honesty review before close.

- [x] `W04.P09.S29` - Add roundtrip plus anti-tautology coverage for divergence facts, the setup-incomplete state, and resume projection; `src/cadrumo/application/user_profile/tests/`.
- [x] `W04.P09.S30` - Verify the portable-export shape against the compatibility lifecycle for every schema addition; `src/cadrumo/domain/user_profile/_portable_export.py`.
- [x] `W04.P09.S31` - Author the user-facing setup-flow documentation through the documentation workflow with command conformance green; `docs/how-to/`.
- [ ] `W04.P09.S33` - Run the fresh-context campaign-close honesty review and persist the close audit with every surfaced item tracked; `.vault/audit/`.
- [ ] `W04.P09.S37` - Add the AST gate asserting every tr(CONSTANT) call site's constant name carries the locale-key naming convention, closing the scanner-invisible-constant concealment class repo-wide; `src/cadrumo/locales/tests/`.

## Description

This plan executes the accepted `2026-07-23-profile-setup-flow-adr` (paged
profile setup flow with dynamic copy assembly and cotejo censal), grounded
in `2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research`
and `2026-07-23-profile-setup-flow-integration-shape-audit`.

The flow consumes the `tui-wizard-substrate` FlowEngine and FlowDefinition
contract, which lands under its own ADR and plan; Wave W03 depends on that
contract being available. The plan therefore front-loads every
substrate-independent deliverable (Wave W01) and the catalogue re-sequence
that runs on the current forward-only runner (Wave W02), so operator value
lands before the substrate integration begins.

## Steps

## Parallelization

Waves are sequenced by default: W01 must land before W03 (the lifecycle
state, reverse index, and parser are W03 inputs), while W02 may run in
parallel WITH W01 (it touches only the catalogue section order and its
gates, none of W01's files). W03 additionally hard-depends on the
`tui-wizard-substrate` FlowEngine contract having landed. Inside W01 the
three phases are mutually independent (P01 lifecycle and events, P02
grounding projections, P03 G313 ingestion) and may run concurrently,
except W01.P01.S01 (derivation-path reconciliation), which must complete
before W03.P06 wires any commit path. Inside W03, P05 precedes P06-P08;
P07 and P08 are mutually independent. W04 is strictly last.

## Verification

- Every step closed with a matching exec record (plan-closure discipline).
- The setup-incomplete lifecycle state is refused by
  `require_profile_ready_for_modelo_work` with an instructive refusal, and
  the event contract test pins the new emission sites (W01.P01).
- `python -m cadrumo.locales scaffold --check` and the parity/honesty
  gates are green after every catalogue change (W02.P04, W03) - the
  `profile` namespace is a dynamic translation root invisible to static
  scanning, so these gates are the mechanical enforcement.
- `validate_user_profile_registry_contract` passes at registry build for
  every schema addition (divergence facts, setup-incomplete marker).
- The re-sequenced flow constructs cleanly at import (the WizardFlow
  validators enforce visible_when ordering) and the documented-command
  conformance gate plus the nitpicky docs build stay green.
- Roundtrip + anti-tautology coverage exists for every new persisted
  surface (divergence facts, setup-incomplete state, resume projection)
  per the roundtrip discipline; no mocks, skips, or xfails.
- The cotejo phase adopts nothing automatically: a regression proves
  artefact facts never gain an official evidence tier and the calendar
  posture is unchanged.
- Full-tree `uv run --no-sync pytest --collect-only -q` is clean at each
  phase close, with owner-triage for any peer-campaign red per the
  full-tree-gate discipline.
- The campaign close runs the fresh-context honesty review and persists
  its audit before the plan is declared structurally complete.
