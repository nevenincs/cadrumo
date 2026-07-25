---
tags:
  - '#exec'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S08'
related:
  - "[[2026-07-25-account-distribution-standard-plan]]"
---




# DONE. The day-one checklist a new product follows is written as a numbered sequence covering the version authority, the two workflows and the no-tag-trigger requirement, the three-property channel-set evaluation, the two shared-repository files, workload identity federation, and the name-derivation rule. Placed in RELEASING.md rather than under docs/ deliberately, on two grounds, it is maintainer rather than taxpayer-facing documentation and docs/ is the taxpayer surface, and the fail-closed documentation claims gate scans docs/ for acquisition claims so a checklist quoting install commands there would correctly red the gate

## Scope

- `RELEASING.md`

## Description

- Write the day-one checklist as six ordered items covering the version authority, the two workflows, the channel-set evaluation, the shared-repository files, federation registration, and name derivation.
- Rewrite the arming section, which still instructed operators to serve Scoop from this repository.
- Renumber the arming steps after the two Scoop and Homebrew items collapsed into one.

## Outcome

A sibling product can be enrolled without rediscovering the shape. The checklist states the fixed cost explicitly and states that it does not grow with the number of products already shipping, because that invariance is the property the whole standard is chosen for.

The arming instructions no longer contradict the ruling. One repository variable and one secret now serve both channel pushes, where the previous text told the operator that Scoop needed neither.

## Notes

The plan step named `docs/` as the scope and the checklist was deliberately not put there, on two independent grounds.

The first is audience. The documentation site is the taxpayer-facing surface; a day-one product-enrolment checklist is maintainer documentation and belongs with the release procedure it extends.

The second is mechanical, and would have bitten. The documentation claims gate is fail-closed and scans every user-facing page under `docs/` for acquisition claims. A checklist quoting install commands there would have been read as advertising those channels ahead of their evidence and would have correctly reded the gate. The options were to place it outside the scanned surface or to weaken the gate, and weakening a fail-closed gate to fit a document is the wrong trade.
