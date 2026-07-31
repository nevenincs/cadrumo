---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:209b584717c129a4df0324d5198cf0b6fc40e540458bbf17d1627676b4b73f58'
step_id: 'S255'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Make every accepted as_of argument participate in revision validity selection or reject it explicitly instead of silently ignoring it

## Scope

- `src/cadrumo/domain/calculations/registry/_queries.py`
- `src/cadrumo/application/modelo/_registry_discovery.py`

## Description

- Enumerate every public entry point on both cited modules that accepts an as-of argument.
- Classify each as honouring the argument in revision selection or refusing it explicitly.
- Confirm no entry point accepts and silently ignores it, which is the defect this step names.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

The fix is committed under `b832ad7b03`, which names this step's sibling in the quality-backlog plan. Both cited modules were checked directly rather than trusted from that message.

In the query service the unscoped resolver refuses. It raises before doing any work, with a message that states why the argument cannot be honoured on that path and names the scoped alternative that can. The reasoning is sound rather than merely convenient: the unscoped path selects the latest revision by period and has no filing-year context to gate a date against a revision's validity window, so honouring the argument there is not possible, and accepting it silently would be the accepted-parameter lie this contract closes.

On the scoped paths the argument genuinely participates. The scoped resolver forwards it to the authority snapshot call as the point-in-time selector, and the year-scoped bindings query filters candidate revisions by comparing the date against each revision's `valid_from` and `valid_to`, so a date outside every declared window yields no covering revision and refuses rather than falling back to the current view. That is participation in selection, not decoration.

In the discovery facade every unscoped wrapper calls a shared refusal helper before delegating, and the helper names the scoped form that honours the argument, so the operator is told where to go rather than merely refused. The scoped wrappers forward the argument to the service. Each unscoped public entry point was checked individually rather than inferred from the helper's existence.

No entry point on either module accepts the argument and ignores it. No change was needed or made.

## Notes

Semantic CODE search is degraded and reports itself healthy, so both modules were enumerated by targeted grep over every occurrence of the argument name and read at each site, rather than sampled.

This is the only one of the four P25 steps with a sibling counterpart, and the sibling's file citations match this step's, so unlike S250 and S252 there was no citation drift to resolve here.
