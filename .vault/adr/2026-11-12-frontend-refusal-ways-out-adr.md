---
tags:
  - '#adr'
  - '#frontend-refusal-ways-out'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:727a22517eef295f0af7c1a90ecf9da556a0940892d31e25b687f78027b0e0db'
related:
  - "[[2026-11-02-operation-refusal-words-adr]]"
  - "[[2026-11-03-backend-served-surface-adr]]"
  - "[[2026-11-11-cli-action-envelope-precondition-alternative-actions-adr]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-10-23-desktop-ledger-editor-adr]]"
  - "[[2026-10-23-desktop-modelo-workspace-adr]]"
  - '[[2026-11-12-frontend-refusal-ways-out-reference]]'
---

# `frontend-refusal-ways-out` adr: `One refusal component per frontend: served words, primary action, ordered alternatives, no way out` | (**status:** `accepted`)

## Problem Statement

Every refusal verdict (`PreconditionVerdictSnapshot`, `native/desktop/frontend/src/shell/modeloContract/modelo.ts:994`) now carries served refusal words, a primary recovery action, an ordered list of alternative actions, or a no-recovery outcome. Neither frontend reads the alternatives. The window renders the primary action only in the Modelo area and one of nine Ledger next-step kinds, and some Ledger saves replace the served refusal with window text. The TUI prints the primary action as a CLI command line and keeps a hand table naming 12 of about 59 catalogue actions. A decision is needed now because each new refusal kind otherwise grows a fourth hand-written variant.

## Considerations

- Served words only: `2026-11-02-operation-refusal-words-adr` and `2026-11-03-backend-served-surface-adr` forbid mapping a code, condition id or action id to a sentence in a frontend.
- `2026-11-11-cli-action-envelope-precondition-alternative-actions-adr`: primary first, alternatives in served order, never sorted, never beside `no_recovery_outcome`; its clause "the window and TUI show the primary door only until the freeze lifts" is satisfied for the frontend paths, which the operator unfroze on 2026-11-12.
- `2026-08-24-tui-modelo-workspace-interface-adr` D7: refused primary actions stay visible and disabled with a stable reason; TUI admission and dispatch are owned by TUI route and action registries.
- The operator action catalogue (`src/cadrumo/application/operator_actions/catalogue.py`) names `action_id` and `target_command_key` only: no action has served words today.

## Considered options

- Keep per-area rendering and add alternatives where each area reads verdicts. Rejected: four divergent variants already exist; the drift repeats per refusal kind.
- One component per frontend fed by served words for every action (chosen).
- Frontend label tables keyed by action id, generated from locale keys. Rejected: a frontend-held map from action id to words is the authored vocabulary the served-surface ADR forbids, and it drifts silently.

## Constraints

- The backend serves `action_words` and `action_words_language` on the primary action and on each alternative, and `no_recovery_words` on a verdict without a way out (backend ask routed by PRIME). Until served, a frontend shows the refusal words and no action control, never an invented label.
- A frontend authors no action wording and never reorders, filters or deduplicates the served list.
- Routing is by `target_command_key` of the action through each frontend's existing closed lists: the window's host-admitted definitions and places; the TUI's route and action registries. An action with no admitted place is shown as served words, disabled, with the generic chrome reason "not available here"; it is never dropped and never rendered as a CLI line.
- Arguments come only from `argument_bindings`; a non-empty `missing_argument_names` opens the destination's form for those arguments rather than submitting.
- `conditionality` is shown as served; a conditional action is not presented as certain.

## Implementation

We will add one refusal component per frontend and replace every area-local refusal rendering with it.

- Window: `RefusalNotice` in `native/desktop/frontend/src/components/` taking a verdict plus the operation detail: served refusal words, a primary action button, the alternatives as secondary controls in order, or the no-recovery sentence. A pure `routeAction(target_command_key, bindings)` resolves a window place from the host-admitted lists. Storybook covers: words only, primary only, primary with two alternatives, conditional action, missing arguments, unroutable action, no way out, and the pre-backend state (no action words).
- TUI: one `RefusalPanel` widget and an action-to-destination router over the route registry, used by the operation modal, the workbench and operation results; the CLI command line is removed from those surfaces.
- Hypothesis that may change: the window component name and the exact place resolver shape.

## Rationale

A single component per frontend makes the next backend refusal kind a data change, not a UI change. Serving action words keeps both frontends free of tax wording and lets the CLI, TUI and window say the same thing. Routing by `target_command_key` reuses the closed lists both frontends already enforce.

## Consequences

- Both frontends lose their hand-kept action tables; a new action appears with its words once the backend serves them.
- Until the action words are served, refusals show words without an action control; this is a visible regression for the Modelo area's primary action, accepted to avoid a temporary hand table. Reconsider if the backend ask is declined.
- The TUI needs a destination for each routable action; actions without one stay visibly disabled, which exposes TUI coverage gaps rather than hiding them.
