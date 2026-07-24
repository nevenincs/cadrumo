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

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- RETIRED: S32 -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `profile-setup-flow` plan

## Wave `W01` - Substrate-independent foundations

Land every flow deliverable that does not depend on the tui-wizard-substrate FlowEngine: the setup-incomplete lifecycle state and early-mint groundwork, CENSO event reconciliation, the legal-refs reverse index and copy-reference gates, the G313 artefact parser, and the derivation-path reconciliation the ADR hands to plan scope.

<!-- One-line headline summary plan. -->

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
- [ ] `W03.P07.S24` - Convert the descendiente and repair verbs into deep-link doors into the flow and delete their bespoke prompt loops in the same change; `src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [ ] `W03.P07.S25` - Convert the apoderado verb into a door that hosts the flow pages while routing writes to the ApoderadoService namespace, never profile facts; `src/cadrumo/entrypoints/cli/_config/_apoderado.py`.

### Phase `W03.P08` - Cotejo censal phase

Wire the compare-select reconciliation of flow answers against the parsed G313 fact set with defer-as-divergence, notices, and the reconciled CENSO_APPLIED emission.

- [ ] `W03.P08.S26` - Build the cotejo compare-select reconciliation of flow answers against the parsed G313 fact set with keep, adopt, and defer decisions; `src/cadrumo/application/wizard/`.
- [ ] `W03.P08.S27` - Persist deferred divergences as typed facts at commit and surface warning notices on later profile reads; `src/cadrumo/application/user_profile/`.
- [ ] `W03.P08.S28` - Emit CENSO_APPLIED at cotejo artefact-apply and pin the emission site in the event contract test; `src/cadrumo/application/user_profile/`.

## Wave `W04` - Hardening and close

Roundtrip and parity coverage for every new persistence surface, documentation and conformance sweeps, and the campaign-close honesty review.

### Phase `W04.P09` - Roundtrips, docs, and honesty close

Roundtrip and anti-tautology coverage for the new persistence surfaces, parity and conformance sweeps, user documentation, and the fresh-context honesty review before close.

- [ ] `W04.P09.S29` - Add roundtrip plus anti-tautology coverage for divergence facts, the setup-incomplete state, and resume projection; `src/cadrumo/application/user_profile/tests/`.
- [ ] `W04.P09.S30` - Verify the portable-export shape against the compatibility lifecycle for every schema addition; `src/cadrumo/domain/user_profile/_portable_export.py`.
- [ ] `W04.P09.S31` - Author the user-facing setup-flow documentation through the documentation workflow with command conformance green; `docs/how-to/`.
- [ ] `W04.P09.S33` - Run the fresh-context campaign-close honesty review and persist the close audit with every surfaced item tracked; `.vault/audit/`.

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

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

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
