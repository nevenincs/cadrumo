---
generated: true
tags:
  - '#index'
  - '#tui-wizard-substrate'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:db13ac78fc45c5f45b1ca4062cc013f2b89f6b7afc61a1226789f225a2b18848'
related:
  - '[[2026-07-23-tui-wizard-substrate-W01-P01-S01]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P01-S02]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P02-S03]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P02-S04]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P02-S05]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P02-S06]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P03-S07]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P03-S08]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P03-S09]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P03-S10]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P04-S11]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P04-S12]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P04-S13]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P05-S14]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P05-S15]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P05-S16]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P05-S17]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P06-S18]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P06-S19]]'
  - '[[2026-07-23-tui-wizard-substrate-W02-P06-S20]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P07-S21]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P07-S22]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P07-S23]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P08-S25]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P08-S26]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P08-S31]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P09-S27]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P09-S28]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P09-S29]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P09-S30]]'
  - '[[2026-07-23-tui-wizard-substrate-W03-P09-S32]]'
  - '[[2026-07-23-tui-wizard-substrate-adr]]'
  - '[[2026-07-23-tui-wizard-substrate-plan]]'
  - '[[2026-07-23-tui-wizard-substrate-research]]'
---

# `tui-wizard-substrate` feature index

Auto-generated index of all documents tagged with `#tui-wizard-substrate`.

## Documents

### adr

- `2026-07-23-tui-wizard-substrate-adr` - `tui-wizard-substrate` adr: `paged TUI wizard substrate` | (**status:** `accepted`)

### exec

- `2026-07-23-tui-wizard-substrate-W01-P01-S01` - Declare the substrate closed value sets (widget kinds including repeating-group and compare-select, page status including stale and deferred, flow mode, checkpoint availability) as StrEnums
- `2026-07-23-tui-wizard-substrate-W01-P01-S02` - Pin the enum member sets and StrEnum token contract with real-behavior tests
- `2026-07-23-tui-wizard-substrate-W01-P02-S03` - Author the strict frozen FlowDefinition family (flow, section, page, choice, copy-reference, branching predicate, repeating group, compare-select) with build-time validators for unique ids, forward-only references, and reference-not-literal copy slots
- `2026-07-23-tui-wizard-substrate-W01-P02-S04` - Port the widget validators and add the typed validator slots (per-answer, section-exit, flow-scope) returning i18n message keys with redacted diagnostics
- `2026-07-23-tui-wizard-substrate-W01-P02-S06` - Prove the definition contract with build-time validator tests covering duplicate ids, non-forward references, literal-copy refusal, and repeating-group shape
- `2026-07-23-tui-wizard-substrate-W01-P03-S07` - Implement the immutable FlowState and the pure transition engine (answer, next, back, jump, reset, restart) with per-transition visibility recompute and staleness marking
- `2026-07-23-tui-wizard-substrate-W01-P03-S08` - Implement the review projection (per-question status glyph set, jump targets, submit eligibility requiring all required valid and zero stale) and the deferred-status surfacing
- `2026-07-23-tui-wizard-substrate-W01-P03-S09` - Cover complete navigation scenarios (back, jump, gating-answer change marks dependents stale, reset, restart, repeating-group instances, deferral) with engine transition tests
- `2026-07-23-tui-wizard-substrate-W01-P03-S10` - Expose the substrate public facade with an explicit __all__ consumed only via top-level re-exports
- `2026-07-23-tui-wizard-substrate-W03-P08-S25` - Migrate the modelo work wizard consumer onto the engine frontends
- `2026-07-23-tui-wizard-substrate-W01-P02-S05` - Bridge the existing wizard catalogue vocabulary into FlowDefinition while keeping the compile_profile_keys projection and the register_wizard_catalogue and register_project_answers core slots fed unchanged
- `2026-07-23-tui-wizard-substrate-W02-P04-S11` - Build the sequential line-mode frontend over the engine, absorbing the questionary prompter role and retaining the translated unsupported-console refusal and IO-injection contract
- `2026-07-23-tui-wizard-substrate-W02-P04-S12` - Build the scripted intent driver preserving the canonical-answer underflow and overflow drift detection
- `2026-07-23-tui-wizard-substrate-W02-P04-S13` - Drive the line-mode frontend headlessly through pipe input and assert prompt, validation, and refusal behavior
- `2026-07-23-tui-wizard-substrate-W02-P05-S14` - Add the textual dependency (MIT, verified conflict-free) and refresh the lockfile
- `2026-07-23-tui-wizard-substrate-W02-P05-S15` - Build the full-screen application shell and the question-page screen with the fixed zones (header progress, prompt, help, badge, format hint, widget, live validation line, answer echo, keybinding footer)
- `2026-07-23-tui-wizard-substrate-W02-P05-S16` - Build the review screen with per-question status glyphs, jump-to-edit, and the submit gate wired to the engine's review projection
- `2026-07-23-tui-wizard-substrate-W02-P05-S17` - Cover full-screen navigation, live validation, and review-submit scenarios headlessly with the Textual Pilot driver
- `2026-07-23-tui-wizard-substrate-W02-P06-S18` - Implement the render-time copy assembler resolving i18n keys and typed schema and locale references, refusing literal strings and unresolvable references loudly
- `2026-07-23-tui-wizard-substrate-W02-P06-S19` - Scaffold the new help, format-hint, and failure-mode key namespaces across all four catalogues through the locales CLI, never hand-editing the yml files
- `2026-07-23-tui-wizard-substrate-W02-P06-S20` - Prove copy resolution against real schema and locale sources including the four-locale parity of the new namespaces
- `2026-07-23-tui-wizard-substrate-W03-P07-S21` - Define the per-mode checkpoint port protocol with the declared no-op arm and the frontend honesty surface (save-and-exit disabled with an explicit message when checkpointing is unavailable)
- `2026-07-23-tui-wizard-substrate-W03-P07-S22` - Implement the resume projection rebuilding FlowState from persisted canonical values with current-definition re-validation, stale landing for mismatches, and cursor at first unanswered visible question
- `2026-07-23-tui-wizard-substrate-W03-P07-S23` - Prove resume re-validation, definition-change stale landing, loud no-op discard, and count-only diagnostics
- `2026-07-23-tui-wizard-substrate-W03-P08-S26` - Retire the one-shot runner and prompter surfaces with every consumer moved in one atomic explicit-path commit, running collect-only clean immediately before the commit and regenerating apidocs stubs in the same commit
- `2026-07-23-tui-wizard-substrate-W03-P08-S31` - Migrate the amend wizard consumer onto the engine frontends, removing its local one-shot prompt helper
- `2026-07-23-tui-wizard-substrate-W03-P09-S27` - Land the parity regression proving the scripted, line-mode, and full-screen paths produce identical answers and validation verdicts for a shared definition
- `2026-07-23-tui-wizard-substrate-W03-P09-S28` - Run the locale parity, translation honesty, and scaffold check gates green for the substrate key namespaces
- `2026-07-23-tui-wizard-substrate-W03-P09-S29` - Run the docs build and documented-command conformance gates green, with owner triage recorded for any unrelated peer failures
- `2026-07-23-tui-wizard-substrate-W03-P09-S30` - Run the full src collect-only and suite gates with owner-distinguished triage of the results
- `2026-07-23-tui-wizard-substrate-W03-P09-S32` - Land the bounded-fstring coverage gate, every dynamic tr or copy-reference site over an enum must carry its registry registration in the same commit, with the three campaign incidents as its seed cases

### plan

- `2026-07-23-tui-wizard-substrate-plan` - `tui-wizard-substrate` plan

### research

- `2026-07-23-tui-wizard-substrate-research` - `tui-wizard-substrate` research: `paged TUI wizard substrate`
