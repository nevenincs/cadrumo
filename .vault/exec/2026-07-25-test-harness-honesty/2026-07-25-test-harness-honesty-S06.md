---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S06'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
  - "[[2026-07-25-test-harness-honesty-adr]]"
---

# VERIFIED-SOUND RECORD, the held-serial escalation mechanism is unwired by design rather than dead code, recorded so a later reader does not fix a mechanism that is deliberately inert

## Scope

- `src/cadrumo/tests/_marker_hook.py`

## Description

- Search the whole source tree for the held-serial symbols and confirm they resolve only inside their defining module.
- Read the commit that introduced them rather than inferring intent from the absent call sites.
- Record the discriminator that separates staged-inert from rotted, not just the conclusion.

## Outcome

Verified sound. No code change, and none is wanted.

The five controller-side held-serial helpers resolve only within their own defining module; a tree-wide search for the symbols returns no consumer anywhere else. That evidence is accurate, and on its own it reads as dead code. The conclusion is nonetheless wrong, and the commit that introduced them is what settles it: its subject states in as many words that it lands the controller half of the refusal INERT, and its body records that nothing outside the module references the helpers, that behaviour is unchanged until a conftest registers the hooks, and why landing the unwired half is preferable to holding it in a working tree.

So the absent references are the documented design, not rot. Recorded here because the misclassification is the actionable part: an auditor who reaches "five symbols, one file, no callers" and stops produces a ticket to delete or wire a mechanism its author deliberately staged, and in a shared worktree that ticket can be actioned by someone who never reads the commit message.

The discriminator is cheap and worth stating plainly: before calling a symbol dead, read the commit that introduced it. Absence of callers is evidence about the call graph, not about intent.

The genuine open question is not whether the helpers are dead but whether to wire them. That is a live decision with a real cost, because wiring changes what every run reports, so it belongs to an owner rather than to a cleanup sweep. It is deliberately left open here.

## Notes

Semantic code search was degraded throughout this session and reported itself healthy: the code index held 188 sections against roughly 4546 files, with an available status and an empty degraded-reasons list. That is a regression from the roughly 1027 sections recorded when S01 landed. Two deliberately unrelated probes returned the same file at noise-level similarity, which is the behavioural field test the audit prescribes for a truncated index.

Discovery for this step was therefore by direct reads, targeted symbol search over the tree, and reading the introducing commit, never by semantic search. Tracked as S02 and S03 of this plan, both external to this repository.
