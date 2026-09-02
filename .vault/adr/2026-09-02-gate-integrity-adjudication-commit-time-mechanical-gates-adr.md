---
tags:
  - '#adr'
  - '#gate-integrity-adjudication'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c31ad2630543eb5b5b045655ef9603baa164e8943820cf19128ccdc88622a990'
related:
  - "[[2026-09-02-gate-integrity-adjudication-tui-entrypoint-contracts-adr]]"
---

# `gate-integrity-adjudication` adr: `mechanical gates stay verify-only and out of commit time` | (**status:** `accepted`)

## Problem Statement

Four mechanical gates - formatting, lint style, relative-import shape and
dependency declaration - have each gone green and regressed repeatedly while
batches land. Every regression is mechanically fixable, and the repository
already carries a pre-commit runner configuration, so the natural proposal is to
give those gates to a commit-time hook and have the fixes applied automatically.

A decision is needed because the proposal's cost is not visible from the gate
results. Several agents commit into this worktree concurrently, and a commit-time
hook is the one gate position that manipulates the working tree of writers who did
not invoke it.

## Considerations

- The repository already made this decision and recorded it. The runner configuration
  states that every hook is verify-only, that no autofixer runs at commit time, and
  that the commit hook script is deliberately not installed.
- Its recorded rationale is an incident in this repository: the runner's stash and
  restore step lost work when an autofixing hook modified the staged tree mid-commit and
  the rollback conflicted with concurrently-edited files in the worktree.
- That failure mode is not historical. Uncommitted work in this repository was destroyed
  by a stash on the same day this question was asked, which is independent corroboration
  of the exact hazard the policy was written against.
- The stash and restore step is a property of running hooks against staged content, not
  of autofixing. A verify-only hook set still saves and restores unstaged changes, so
  installing the hook at all opens the window, and the window is as long as the slowest
  hook.
- The formatting and lint gates are already declared in the runner configuration in
  verify-only form. What is absent is not the gate but the installed commit-time trigger,
  which is the part that was withheld on purpose.
- Measured on the live tree, the two currently-red gates report drift in files that other
  contributors are actively editing. An autofixing hook would have rewritten those files
  on someone else's commit, which is the one-writer boundary the project's worktree
  discipline draws.
- Cost is not the obstacle. Three of the four gates complete in seconds over the whole
  tree; the relative-import gate is the slow one at roughly forty seconds, and all four
  are already reachable from the aggregate static gate.
- The repository already has the shape a cheap pre-commit check would take: a
  change-scoped verb exists for documentation, bounding work by the change rather than
  the tree, and one locale gate is written to read committed blobs and write nothing
  precisely so it stays compatible with the verify-only policy.

## Considered options

**Install the commit hook with autofixers for the four gates.** Rejected. It combines
both hazards: the stash window, and rewriting files belonging to concurrent writers on a
commit that did not touch them.

**Install the commit hook, verify-only.** Rejected. It drops the rewrite hazard but keeps
the stash window, which is the mechanism that has actually destroyed work here, and it
would block commits on drift a contributor did not introduce.

**Add the two absent gates to the runner configuration without installing the hook.**
Rejected as motion without effect. Both already run under the aggregate gate, and adding
them to an uninstalled hook set changes nothing about when a regression is noticed.

**Reaffirm the policy and add a change-scoped verification recipe.** Chosen. It leaves
the commit path untouched and gives the operator and agents a seconds-long check over
only the paths a change touches, which is the moment and the scope at which these
regressions are actually actionable.

## Constraints

- Any check offered as a pre-commit habit must not manipulate git state. It reads the
  change and the working tree and writes nothing, so it cannot lose work however it is
  interrupted.
- It must be scoped to the paths of the change under inspection. A whole-tree check
  reports drift owned by other writers and trains its users to ignore it, which is worse
  than not running.
- Automatic repair stays a separate, explicitly invoked step. The repository already
  exposes the repair verbs, and this record does not move them.

## Implementation

The verify-only policy stands, and the commit hook remains uninstalled. Its recorded
rationale is left in place and is now corroborated rather than revised.

A change-scoped verification recipe is added beside the existing static gates. It
resolves the Python paths a change touches against a base reference, and runs the
formatting and style checks over exactly those paths, reporting nothing on a clean
change. It manipulates no git state, rewrites no file, and its cost is bounded by the
size of the change rather than the size of the tree, so it is usable as a habit
immediately before committing.

The relative-import and dependency gates are deliberately not folded into it. Both are
whole-tree predicates whose answer does not decompose to the changed paths, and the
aggregate static gate already owns them.

The recipe is a convenience, not a barrier. Nothing enforces it, which is the point: in a
worktree with concurrent writers, the enforcement position that would make it binding is
the same position that has already cost this repository work.

## Rationale

The decisive fact is that the proposal has been tried here and the outcome is recorded.
The configuration's own rationale describes work lost to the interaction between an
autofixing hook and concurrently-edited files, and that same interaction destroyed
uncommitted work in this repository on the day the question was reopened. A decision to
install now would be overturning a policy on the strength of the inconvenience it causes
while ignoring the loss it prevents.

The concurrency detail is what makes the usual argument fail. A commit-time formatter is
ordinarily safe because one author owns the tree; here several writers do, so the hook
would act on a tree its invoker did not author, and the currently-red files demonstrate
that this is the live case rather than a hypothetical one.

The change-scoped recipe wins because it addresses the actual complaint. The regressions
persist not because the gates are missing but because the only way to notice one is a
slow whole-tree run nobody performs between batches. A seconds-long check over the changed
paths restores the feedback at the moment it is actionable, and it does so from the
position that carries no risk.

## Consequences

The commit path stays free of tooling that can lose work, and the one-writer boundary
holds: no contributor's commit rewrites another's in-flight files.

Regressions remain possible, because nothing blocks a commit that introduces one. That is
accepted deliberately, and the recipe narrows the window in which one goes unnoticed
rather than closing it.

The recipe adds a surface that must stay correct as the gates evolve, and it deliberately
covers only the two gates that decompose to changed paths, so it can report clean while a
whole-tree predicate is red. It is a fast preflight and not a substitute for the aggregate
gate, and it should not be extended into one.
