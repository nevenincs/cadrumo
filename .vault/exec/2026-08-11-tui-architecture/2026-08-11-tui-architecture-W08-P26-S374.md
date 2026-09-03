---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:cefe8eec29d64bd7437134fcab6848fd58a787bca36844471b6ec42e5122dafe'
step_id: 'S374'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Record the winning workbench layout and interaction parameters in the amended navigation decision execution evidence

## Scope

- `.vault/exec/2026-08-11-tui-architecture/`

## Changes

- `A` `.vault/exec/2026-08-11-tui-architecture/2026-08-11-tui-architecture-W08-P26-S374.md`

## Measured decision evidence

### Decision

Retain the **due-driven Home** as the production workbench layout. It exposes
the application-ranked work and portfolio state directly, while the alternate
task-launcher prototype trades that glanceability for one compressed chooser.
The measured keyboard costs below do not show a compensating speed advantage
for the task launcher on the shared ready fixture.

The retained information order is:

1. no more than three application-ranked next actions;
2. resumable Declarations;
3. a chronological three-row filing agenda; and
4. compact, separately labelled Ledger, Messages, and AEAT-evidence signals.

At widths of 120 columns and above, Actions and Declarations occupy the
two-thirds main column and the agenda plus source signals occupy the one-third
side column. Below 120 columns, the same content becomes one ordered column:
Actions, Declarations, Agenda, then the compact source signals. Both modes use
one page-level vertical scroll owner. Tables own no horizontal overflow and no
nested vertical scrolling.

### Measurement population and result

The real Textual compositor exercised 84 passing cases:

- 64 dense frames: 2 candidates x 4 terminal sizes (`80x24`, `100x30`,
  `120x40`, `200x50`) x 2 themes x 4 shipped locales (`es`, `en`, `ca`,
  `hu`);
- 14 terminal-floor frames: 2 candidates x all 7 fixture states; and
- 6 focused interaction, locale, restoration, and authority checks.

Every dense frame had `max_scroll_x == 0` for every table, no widget painted
past the horizontal screen edge, no scrolling screen, and at most one visible
vertical owner, which when present was the outer page scroll. The locale run
proved different operator copy in all four shipped locales while preserving
the same semantic target identities. The seven-state floor run preserved
ready, locked, stale, never-captured, unavailable, available-empty, and blocked
meanings without turning unknown data into zero.

### Exact ready-fixture key costs

Counts start at each candidate's initial focus and include the confirming
`Enter` key:

| Target | Due-driven | Task launcher |
| --- | ---: | ---: |
| Highest-ranked action | 1 (`Enter`) | 1 (`Enter`) |
| First resumable Declaration | 2 (`Tab`, `Enter`) | 4 (`Down` x3, `Enter`) |
| Nearest agenda item | 3 (`Tab` x2, `Enter`) | 5 (`Down` x4, `Enter`) |
| Second resumable Declaration | 3 (`Tab`, `Down`, `Enter`) | Not in the five-target preview |

The task launcher deliberately caps its preview at five semantic targets
rather than flattening all nine projected rows. That keeps every offered
target within four arrow presses plus `Enter`, but hides two additional
Declarations and two additional agenda rows that the due-driven layout keeps
directly reachable.

### Retained interaction parameters

- Initial focus is the highest-ranked next action.
- Each list is one `Tab` stop; arrow keys move within it and `Enter` confirms
  the selected semantic target.
- `Tab` order follows Actions, Declarations, then Agenda.
- `Escape` returns without executing a business action.
- Focus restoration uses action identity, declaration identity, or the agenda
  natural address, and survives responsive resize and reordered projections.
- `Ctrl+P` remains the global task-launcher accelerator in the accepted shell
  design. It was outside these prototype screens and was not measured by the
  S373 compositor run; its production proof remains with global workbench
  search and command-palette composition.

These measurements establish layout containment, scroll ownership, locale
rendering, keyboard mechanics, and semantic restoration for synthetic
projections. They do **not** establish real-operator preference, task success,
assistive-technology behavior, or usability/accessibility compliance.
