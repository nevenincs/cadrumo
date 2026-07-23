---
generated: true
tags:
  - '#index'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
related:
  - '[[2026-07-23-tui-wizard-substrate-W01-P01-S01]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P01-S02]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P02-S03]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P02-S04]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P02-S06]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P03-S07]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P03-S08]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P03-S09]]'
  - '[[2026-07-23-tui-wizard-substrate-W01-P03-S10]]'
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

### plan

- `2026-07-23-tui-wizard-substrate-plan` - `tui-wizard-substrate` plan

### research

- `2026-07-23-tui-wizard-substrate-research` - `tui-wizard-substrate` research: `paged TUI wizard substrate`
