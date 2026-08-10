---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:0041c43670426077da3fde5614f023a4a8104009562337434c44380fa3fea562'
step_id: 'S34'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Decide how dev tooling lane reds become visible between manual dispatches

## Scope

- `justfile`
- `.github/workflows/ci-full.yml`

## Description

- Weigh the two admissible options against measured evidence rather than against the discomfort of the gap.
- Record the decision, its grounds, and what it does NOT authorise.

## Outcome

**Decision: the dev tree becomes reachable from a lane leads actually run. The alternative is rejected, and it is rejected on evidence that did not exist when the row was written.**

The row admitted two honest options: make these tests reachable locally, or state plainly that dev-tooling reds are invisible between manual dispatches and name someone accountable for noticing. The second was a real close when the row was authored, on the reasoning that a known and owned gap beats an unowned one. Two measured victims have since made it untenable.

The first victim was the one that opened the investigation: fourteen failures in the agent-eval directory, ten of them a live campaign's change, red for hours with no signal, found only because someone reached that directory by hand for an unrelated reason.

The second is the one that settles it. Six failures remain there belonging to an external envelope campaign, whose goldens expect one field where the envelope now emits another. **That campaign cannot see them.** No source-scoped lane reaches the dev tree, and they have no reason to run a directory outside their scope. They will land their work, see green everywhere they look, and never learn.

That is what an accountable-noticer cannot fix. Naming someone to watch a directory works when the person who breaks it can be told; it does not work when the breakage belongs to a team that has no channel into the observation and no reason to look. An option whose whole mechanism is human attention fails exactly where the damage is invisible to the humans concerned, which is where this damage is.

## Notes

What this decision does NOT authorise, stated because a decision row is easiest to over-read. It does not authorise a scheduled run or a nightly, both refused by standing operator ruling, and a remedy the operator has already declined is not a decision but a re-litigation. It does not authorise hosted runners. And it does not authorise the implementation, which is a separate row for a specific reason: making the dev tree locally reachable adds two hundred and forty-six test files to every local invocation for every lead. That is a blast radius, and the discipline that governed the registry enrolment governs this too - the measurement precedes the change, and it is worth remembering that in that case the measurement inverted what all three of us predicted.

So the shape is: this row rules WHAT, the implementing row obtains the number, and the change lands behind it. Ruling the what without the number is not a half-decision, because the alternative was rejected on grounds that no measurement of cost could revive - a cheaper implementation would not make an unreachable campaign reachable by attention.

One caution for whoever takes the implementing row, learned from an adjacent lane today. A run that collects nothing and a run in which everything passes print the same absence of red. Confirm the lane actually collects before treating its output as a measurement, because the failure mode of this particular change is a path that silently selects nothing.
