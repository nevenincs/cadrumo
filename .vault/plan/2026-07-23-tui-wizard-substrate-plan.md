---
tags:
  - '#plan'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
tier: L3
related:
  - '[[2026-07-23-tui-wizard-substrate-adr]]'
  - '[[2026-07-23-tui-wizard-substrate-research]]'
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

<!-- RETIRED: S24 -->

# `tui-wizard-substrate` plan

## Wave `W01` - Core contracts and flow engine

Build the renderer-agnostic substrate core: closed enums, FlowDefinition contract models, and the FlowEngine state machine with full navigation, staleness, and review semantics.

### Phase `W01.P01` - Core enums and typed transitions

Declare the substrate's closed value sets and typed transition intents in core, extending the widget taxonomy with the repeating-group and compare-select kinds and the page-status set.

- [x] `W01.P01.S01` - Declare the substrate closed value sets (widget kinds including repeating-group and compare-select, page status including stale and deferred, flow mode, checkpoint availability) as StrEnums; `src/cadrumo/core/flows.py`.
- [x] `W01.P01.S02` - Pin the enum member sets and StrEnum token contract with real-behavior tests; `src/cadrumo/core/tests/test_flows_enums.py`.

### Phase `W01.P02` - FlowDefinition contract models

Author the strict frozen definition family with copy references, branching predicates, repeating groups, and the section-exit plus flow-scope validator slots, preserving continuity with the existing descriptor vocabulary and the three registration projections.

- [x] `W01.P02.S03` - Author the strict frozen FlowDefinition family (flow, section, page, choice, copy-reference, branching predicate, repeating group, compare-select) with build-time validators for unique ids, forward-only references, and reference-not-literal copy slots; `src/cadrumo/application/flows/_definition.py`.
- [x] `W01.P02.S04` - Port the widget validators and add the typed validator slots (per-answer, section-exit, flow-scope) returning i18n message keys with redacted diagnostics; `src/cadrumo/application/flows/_validators.py`.
- [ ] `W01.P02.S05` - Bridge the existing wizard catalogue vocabulary into FlowDefinition while keeping the compile_profile_keys projection and the register_wizard_catalogue and register_project_answers core slots fed unchanged; `src/cadrumo/application/flows/_bridge.py`.
- [x] `W01.P02.S06` - Prove the definition contract with build-time validator tests covering duplicate ids, non-forward references, literal-copy refusal, and repeating-group shape; `src/cadrumo/application/flows/tests/test_definition.py`.

### Phase `W01.P03` - FlowEngine state machine

Implement the immutable FlowState and the pure transition engine covering answer, navigation, jump, reset, restart, staleness, deferral, and the review projection, with exhaustive transition tests.

- [x] `W01.P03.S07` - Implement the immutable FlowState and the pure transition engine (answer, next, back, jump, reset, restart) with per-transition visibility recompute and staleness marking; `src/cadrumo/application/flows/_engine.py`.
- [x] `W01.P03.S08` - Implement the review projection (per-question status glyph set, jump targets, submit eligibility requiring all required valid and zero stale) and the deferred-status surfacing; `src/cadrumo/application/flows/_review.py`.
- [x] `W01.P03.S09` - Cover complete navigation scenarios (back, jump, gating-answer change marks dependents stale, reset, restart, repeating-group instances, deferral) with engine transition tests; `src/cadrumo/application/flows/tests/test_engine.py`.
- [x] `W01.P03.S10` - Expose the substrate public facade with an explicit __all__ consumed only via top-level re-exports; `src/cadrumo/application/flows/__init__.py`.

## Wave `W02` - Frontends and copy assembly

Build the interaction adapters over the engine: the line-mode frontend, the scripted intent driver, the Textual full-screen frontend, and the render-time copy assembler over schema and locale sources.

### Phase `W02.P04` - Line-mode frontend and scripted driver

Project the engine through a sequential line-mode frontend that absorbs the questionary prompter role and a scripted intent driver that preserves underflow and overflow drift detection, keeping the translated unsupported-console refusal.

- [ ] `W02.P04.S11` - Build the sequential line-mode frontend over the engine, absorbing the questionary prompter role and retaining the translated unsupported-console refusal and IO-injection contract; `src/cadrumo/application/flows/_line_frontend.py`.
- [ ] `W02.P04.S12` - Build the scripted intent driver preserving the canonical-answer underflow and overflow drift detection; `src/cadrumo/application/flows/_scripted.py`.
- [ ] `W02.P04.S13` - Drive the line-mode frontend headlessly through pipe input and assert prompt, validation, and refusal behavior; `src/cadrumo/application/flows/tests/test_line_frontend.py`.

### Phase `W02.P05` - Textual full-screen frontend

Add the textual dependency and build the full-screen application: question-page screen with the fixed zones, review screen with jump-to-edit, keybindings, and headless Pilot coverage of complete navigation scenarios.

- [ ] `W02.P05.S14` - Add the textual dependency (MIT, verified conflict-free) and refresh the lockfile; `pyproject.toml`.
- [ ] `W02.P05.S15` - Build the full-screen application shell and the question-page screen with the fixed zones (header progress, prompt, help, badge, format hint, widget, live validation line, answer echo, keybinding footer); `src/cadrumo/adapters/inbound/tui/`.
- [ ] `W02.P05.S16` - Build the review screen with per-question status glyphs, jump-to-edit, and the submit gate wired to the engine's review projection; `src/cadrumo/adapters/inbound/tui/_review_screen.py`.
- [ ] `W02.P05.S17` - Cover full-screen navigation, live validation, and review-submit scenarios headlessly with the Textual Pilot driver; `src/cadrumo/adapters/inbound/tui/tests/`.

### Phase `W02.P06` - Render-time copy assembler

Resolve every page copy slot by reference against the schema definitions and the four locale catalogues at render time, scaffolding the new help, format-hint, and failure-mode key namespaces through the locales CLI.

- [ ] `W02.P06.S18` - Implement the render-time copy assembler resolving i18n keys and typed schema and locale references, refusing literal strings and unresolvable references loudly; `src/cadrumo/application/flows/_copy.py`.
- [ ] `W02.P06.S19` - Scaffold the new help, format-hint, and failure-mode key namespaces across all four catalogues through the locales CLI, never hand-editing the yml files; `src/cadrumo/locales/`.
- [ ] `W02.P06.S20` - Prove copy resolution against real schema and locale sources including the four-locale parity of the new namespaces; `src/cadrumo/application/flows/tests/test_copy_assembly.py`.

## Wave `W03` - Checkpoint, migration and gates

Wire the checkpoint port, migrate every existing wizard consumer onto the engine, retire the superseded one-shot surfaces atomically, and land the parity and conformance gates.

### Phase `W03.P07` - Checkpoint port and resume

Define the per-mode checkpoint port and the resume projection that rebuilds FlowState from persisted facts, with the no-op declaration surface and loud-discard honesty constraints.

- [ ] `W03.P07.S21` - Define the per-mode checkpoint port protocol with the declared no-op arm and the frontend honesty surface (save-and-exit disabled with an explicit message when checkpointing is unavailable); `src/cadrumo/application/flows/_checkpoint.py`.
- [ ] `W03.P07.S22` - Implement the resume projection rebuilding FlowState from persisted canonical values with current-definition re-validation, stale landing for mismatches, and cursor at first unanswered visible question; `src/cadrumo/application/flows/_resume.py`.
- [ ] `W03.P07.S23` - Prove resume re-validation, definition-change stale landing, loud no-op discard, and count-only diagnostics; `src/cadrumo/application/flows/tests/test_checkpoint_resume.py`.

### Phase `W03.P08` - Consumer migration and retirement

Move the profile create and edit CLI wiring and the modelo work wizard onto the engine, then retire the one-shot runner and prompter surfaces atomically with their consumers per the no-legacy rule.

- [x] `W03.P08.S25` - Migrate the modelo work wizard consumer onto the engine frontends; `src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py`.
- [ ] `W03.P08.S26` - Retire the one-shot runner and prompter surfaces with every consumer moved in one atomic explicit-path commit, running collect-only clean immediately before the commit and regenerating apidocs stubs in the same commit; `src/cadrumo/application/wizard/`.
- [ ] `W03.P08.S31` - Migrate the amend wizard consumer onto the engine frontends, removing its local one-shot prompt helper; `src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py`.

### Phase `W03.P09` - Parity gates and documentation

Land the interactive-versus-non-interactive parity regression, locale parity and honesty gates, apidocs scaffold, and the full-tree collection gate with owner triage.

- [ ] `W03.P09.S27` - Land the parity regression proving the scripted, line-mode, and full-screen paths produce identical answers and validation verdicts for a shared definition; `src/cadrumo/application/flows/tests/test_frontend_parity.py`.
- [ ] `W03.P09.S28` - Run the locale parity, translation honesty, and scaffold check gates green for the substrate key namespaces; `src/cadrumo/locales/`.
- [ ] `W03.P09.S29` - Run the docs build and documented-command conformance gates green, with owner triage recorded for any unrelated peer failures; `docs/`.
- [ ] `W03.P09.S30` - Run the full src collect-only and suite gates with owner-distinguished triage of the results; `src/cadrumo/`.

## Description

Executes the accepted `2026-07-23-tui-wizard-substrate-adr` (rulings D1 to D5),
grounded by `2026-07-23-tui-wizard-substrate-research` and the profile-integration
grounding audit `2026-07-23-profile-setup-flow-integration-shape-audit`. The work
builds the renderer-agnostic paged-wizard substrate: a pure FlowEngine state
machine in the application layer (W01), thin frontends over it (line-mode,
scripted, and Textual full-screen) plus the render-time copy assembler over the
schema and locale sources (W02), and the per-mode checkpoint port, the migration
of every existing wizard consumer, and the closing parity and conformance gates
(W03). The substrate is domain-blind; the profile-setup flow that composes on it
is a separate stream governed by its own ADR and plan. Hard boundaries the ADR
fixes and every Step inherits: no engine or contract type imports the rendering
library, no second flow authority survives (the one-shot runner and prompter are
absorbed and retired atomically), copy slots are references resolved at render
time (schema and locale sources only, never the legal corpus, never literals),
checkpoint implementations route through the owning domain's mutation authority,
and the three registration projections (compile_profile_keys,
register_wizard_catalogue, register_project_answers) keep being fed unchanged.
The profile-setup flow's own plan governs the domain flow, the commit path,
and the derivation-path documentation prerequisite; this plan stays scoped to
the substrate and the migration of existing wizard consumers.

## Steps

## Parallelization

Waves are sequenced: W01 defines the contract every W02 frontend projects, and
W03 migrates consumers only once at least one interactive frontend exists.
Within W01, P01 precedes P02 and P03 (both consume the core enums), and P03
depends on P02's definition models; P02.S04 (validators) and P02.S05 (bridge)
may run in parallel after S03. Within W02, P04, P05, and P06 are mutually
independent once W01 lands and may run as three parallel lanes; inside P05,
S14 (dependency) precedes S15 to S17. Within W03, P07 is independent of P08 and
may run in parallel with it; P08's steps are strictly ordered (S24, then S25,
then the atomic retirement S26, which must not begin until S24 and S25 are
committed); P09 runs last and strictly after P08. Shared-worktree discipline
applies to every lane: explicit-pathspec commits only, abort on foreign WIP in
a target file, and the destructive-git prohibition leads every dispatch brief.

## Verification

Mission success criteria, each mechanically checkable:

- Engine transition tests cover every navigation scenario the ADR names
  (back, jump, gating-change staleness, reset, restart, repeating-group
  instances, deferral, submit-only-from-review) and pass without mocks.
- The frontend parity regression proves scripted, line-mode, and full-screen
  paths yield identical answers and validation verdicts for a shared
  definition.
- A structural gate (import-linter contract or dedicated test) proves no
  engine or contract module imports textual.
- Resume tests prove definition-change re-validation lands mismatches as
  stale, the modify-mode no-op discards loudly, and diagnostics carry counts
  only.
- The compile_profile_keys projection and both core registration slots are
  regression-pinned against the bridged definitions.
- Locale parity, translation honesty, and scaffold-check gates are green for
  the new key namespaces in all four catalogues.
- apidocs scaffold-check, docs build, and documented-command conformance
  gates are green; full-src collect-only is clean or red only with recorded
  owner triage naming unrelated peer signatures.
- No `run_flow`/`Prompter` consumer survives outside the substrate at the
  retirement commit, verified by grep at HEAD, and the retirement commit is
  a single atomic explicit-path commit.
- A fresh-context honesty review runs against this plan's closure summary
  before the campaign is declared structurally complete.

The plan is complete when every Step row is closed and each closed Step has a
matching execution record (or a recorded deferral) per the plan-closure rule.
