---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:8331db55d3e7e2655df4ea030ca7d4091760fdee22fbca5b634071f5c04f25bb'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `W08.P27.S379 full review`

## Scope

Final bounded review of the six host-neutral AEAT Sync routes after the S397
safe-projection and S399 opaque-notification-identity prerequisites. The pass
covered live rendering in every shipped locale, source-state truthfulness,
terminal geometry, semantic identities, operation admission and handoff, and
the boundary with the existing census, declaration-history, calendar, and
operation-supervisor surfaces.

## Findings

### reconciliation-table-overflow | medium | The five-column reconciliation body exceeded its container by two columns

Resolved in the live S379 tranche. The local and AEAT state columns were
reduced by one column each while the natural declaration coordinate retained
its full allocated width. Compositor measurements now report
`max_scroll_x == 0` for both AEAT Sync tables on all six routes at 80, 100, and
120 columns.

### census-row-action-regression | high | The census screen read action fields that the safe S397 census row deliberately does not expose

Resolved in the live S379 tranche. Census rows are again read-only comparison
rows. The only census mutation affordance comes from an action-capable overview
row whose exact action and operation declarations pass the controller's
catalogue and public-contract join. This retains the existing census-review
journey without reintroducing authority on a display DTO or inventing a remote
push control.

### operation-supervisor-is-a-launcher-composition-dependency | informational | S379 cannot itself construct or own the generic supervisor

The typed `AeatSyncOperationHandoffV1` contract now states the actual ownership
boundary: the installed host resolves the pre-admitted request to the canonical
`OperationController` and calls `present_operation_modal`. `OperationModal`
already owns progress, partial/failure outcomes, detach, and cancellation. The
AEAT Sync screen proves one-shot handoff, concurrent/repeat refusal, missing-host
refusal, and sanitized host failure, but it intentionally does not construct
the controller or modal. Wiring that contract is the installed-session work in
S384 and is not claimed here.

### generic-operation-copy-and-missing-filed-pull | high | The screens did not preserve the admitted action's meaning

Resolved. Operation labels now come from a closed exact
action/operation-to-locale-key map after controller admission, never from a
caller-selected generic label. The Filed declarations screen obtains
`operator.live.filed.pull_all` plus `live.filed-history.pull` from the
application-declared overview row and uses the existing one-shot supervisor
handoff. Census retains local review/adoption wording. The notification-list
action has no operation and therefore creates no fake pull button or refusal.

## Recommendations

1. In S384, implement `AeatSyncOperationHandoffV1` with the existing
   `present_operation_modal` facade and canonical operation-controller factory;
   do not replace it with direct operation execution.
2. Keep census review and notification document handling as typed handoffs, and
   route fuller declaration history/calendar journeys to the existing
   Declarations factories rather than expanding these safe summary tables.

## Final verification

The focused suite mounts all six routes in all four shipped locales through the
locale context API. It checks authored headings, column labels, state and
refusal copy, absence of raw enum tokens and translation keys, and invariance of
route IDs and semantic row keys. A second matrix covers known-empty, stale,
locked, never-captured, and unavailable facts for every zone. The 80x24,
100x24, and 120x24 compositor samples have no horizontal table overflow, one
outer vertical-scroll owner, no nested table scrollbar, keyboard-reachable
actions, and textual rather than colour-only source state.

The suite also proves local census-adoption wording with no remote-push control,
no mount-time callback, unread-notification refusal before the document door,
exact action/operation admission, double-submit prevention, missing-host
refusal, sanitized generic failure, and opaque notification focus across
reorder, refresh, resize, and child return.

Final evidence: 60 focused tests passed with all lanes enabled; Ruff lint and
format checks passed; ty passed; basedpyright reported zero errors, warnings,
and notes.

Final result: **CLOSE**. S379 may close. The S384 supervisor bridge remains an
explicit composition dependency, not unfinished business inside the S379
screens.
