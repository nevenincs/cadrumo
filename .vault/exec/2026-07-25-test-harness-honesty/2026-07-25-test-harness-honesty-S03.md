---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-28'
modified: '2026-07-28'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
step_id: 'S03'
---

# FORMALLY DEFERRED with its named mechanism unmeasured, assess whether the code index can converge at all while a committing fleet re-triggers its rebuild through the file watcher, answered in the operative sense on 2026-07-28 by measurement showing non-convergence under fleet load caused by deliberate peer server stop calls from four worktrees against the one machine-global instance rather than by watcher re-trigger, which remains unmeasured and is not measurable from this tree

## Scope

- `external, vaultspec-rag repository not this tree`

## Description

- Separate the question the row asks from the decision the row exists to inform, since the audit answers one and not the other.
- Establish what the audit actually measured, finding deliberate shutdown and contention rather than watcher re-trigger.
- Judge whether the named mechanism is still live after the more fundamental blocker is accounted for.
- Weigh leaving the row open as an action with consequences rather than as a neutral default.
- Close as formally deferred, stating the residual mechanism and the conditions under which it could be measured.

## Outcome

Closed as formally deferred. The assessment reaches a defensible answer for the decision it existed to inform, and the mechanism it names is unmeasured. Both halves are stated because either alone misleads.

Answered: the index does not converge under fleet load, and waiting does not fix it. The audit measures a rebuild from this tree destroyed mid-flight, all three axes left reading `not indexed yet`, vault documents fallen from 16961 to zero, and 57392 code sections left as an orphan of the killed job. The cause is structural rather than incidental — the service and its index are machine-global while the campaigns using them are not, and a campaign actively developing the service stops and starts it as its ordinary loop, recorded as explicit `cli_terminate` shutdowns from four separate worktrees. There is no failure here to wait out, which is the operative question the row was tracking when it observed that the degraded window is not self-limiting.

NOT answered: the mechanism the row names. Nothing measured the file watcher re-triggering a rebuild under a committing fleet. Deliberate shutdown and GPU contention are related conditions, not that one, and the distinction matters because the watcher question survives its resolution — if the machine-global singleton problem were fixed tomorrow, whether a committing fleet can starve a rebuild through watcher re-trigger would still be unknown. This record should not be read as having established it either way.

It is also not measurable from here, on two independent grounds. The watcher and its rebuild scheduling are the discovery service's own code, in a separate repository. And on this host the measurement is unavailable regardless, because a peer campaign holds the machine-global instance and stops it at will, so any observation of a rebuild's progress is confounded by shutdowns that have nothing to do with the watcher. Measuring it needs the service's own repository, or an uncontended host.

Leaving the row open was weighed and rejected as the less safe option. An open row reading "assess whether the code index can converge" invites the next agent to do exactly what the audit records as harmful: queue a rebuild to see whether it converges. That attempt already destroyed partially-present generations once. Closing the row with the destructive-retry finding attached to it removes the invitation, which an open row does not.

Follow-up, named: measure the watcher re-trigger loop in the discovery service's own repository, or on a host not carrying a competing fleet, and do so without a rebuild against a contended machine-global instance.

## Notes

The temptation this record refuses is to treat "the index does not converge" as the whole answer because it is true and was measured. It is true, and it was reached by a different mechanism than the row hypothesised, so presenting it as the row's answer would quietly convert a hypothesis nobody tested into one that was confirmed. The row asked about the watcher and the watcher was not observed.

Worth carrying: the more fundamental blocker made the named one unobservable rather than refuting it. That is a general shape — when a coarser failure dominates, the finer hypothesis does not become false, it becomes unmeasurable, and a closure that does not say so reads later as evidence against the hypothesis.

The audit's own correction is why this row can be closed at all. While the shutdowns were read as crashes of unknown cause, convergence looked like something that might resolve on its own and the row was genuinely open. Once they were identified as deliberate peer shutdowns of a machine-global singleton, the non-convergence became a structural property with a known owner, which is a deferrable condition rather than an open investigation.

No start, stop, index, or rebuild was attempted from this tree during this assessment, on the audit's finding that retrying under contention is destructive. Every statement here about the machine-global instance is carried from the audit and labelled as such; nothing about it was re-measured.
