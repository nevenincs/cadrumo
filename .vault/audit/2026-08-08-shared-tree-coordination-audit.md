---
tags:
  - '#audit'
  - '#shared-tree-coordination'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7860b5db4e5df9670b9d57d5a57cb16099763e18e9f0b459c1f18dff7879b4a9'
related: []
---

# `shared-tree-coordination` audit: bare whole-index sweeps and tree-wide fix verbs

Two mechanisms observed repeatedly in one session, each producing a published state no author intended. Recorded because both are invisible in the artefacts they damage: the commit history reads as ordinary work, and the damaged attribution is only recoverable from an execution record.

### Bare whole-index commits publish other agents' mid-edit state

Four occurrences in a single session, by at least two different peers, all under the subject `feat(cadrumo): land the in-flight source work` or a close variant.

Misattribution is the mild outcome. One sweep took an edit to the storage write policy under an unrelated subject. Another took 132 of the 165 lines of a registry gate change, leaving the module's history showing a peer commit where the bulk of the work is.

The severe outcome is a published broken state. One sweep captured a test module at a moment when its import still named the pre-relocation module, so HEAD briefly could not collect that module. Another captured a new core module together with its author's unfixed import-sort violation, so HEAD briefly carried a lint error that belonged to one agent and was committed by another. Neither breakage had an owner at the moment it landed: the sweeping agent did not author the content and the authoring agent had not yet published.

The exposure window is between edit and commit, and it is short. In the reported cases it was minutes.

**What worked.** Landing the correction as its own single-file pathspec commit, immediately, without reaching for a forbidden verb to undo the sweep. Recording in the execution record that the row's content spans two commits, only one of which names it, so attribution survives where the git history no longer carries it.

**What follows for authors.** Commit in smaller increments than feel natural, and treat every read of a shared file as potentially stale by the time the write lands. Build each edit from the committed bytes rather than the working copy, since a sweep between read and write silently widens what a working-copy-derived patch contains. Verify after the fact with a numstat rather than inspecting the index beforehand.

### A repair verb scoped by a feature flag still ran tree-wide

The annotation-stripping fix verb was invoked with a feature named. It stripped template comments from twenty-six execution records belonging to four other features. The edits were the verb's own sanctioned hygiene transformation and altered no content, but they landed as uncommitted changes in other agents' working copies, where they read as that agent's own unexplained churn.

Leaving them uncommitted for their owners was the right call: committing another agent's records would have compounded a scope error into a false attribution.

**What follows.** A `--fix` on a repair verb is a tree-wide claim unless proven otherwise, whatever scoping argument accompanies it. Preview first, and read the preview's file list rather than its summary count. The same caution applies to any tree-wide generator: a documentation-stub scaffold emits stubs for peers' modules too, and the correct response is to diff each regenerated file and stage only those whose added lines name your own module.

### Why this is recorded rather than codified

The standing worktree-safety rule already forbids the destructive verbs and already prescribes the explicit-pathspec commit and the apply-cached drive. Nothing here contradicts it. What these occurrences add is the observation that **following the rule is not sufficient protection when a peer does not**, and that the resulting damage lands on the compliant agent. That is a coordination fact about this tree at this moment, not a new mandate, and the always-on rule corpus is already load-bearing on every session.

### Consequence observed: a red tree-wide gate whose owner is unrecoverable

The combined-period-string gate and the AEAT-route-literal centralisation gate are both red, and have been for the whole session. The combined-period gate names fourteen offending lines, twelve of them bank-statement fixture filenames of the shape `bank_bbva_2026Q1.csv` across the financial tabular providers and the core tabular-dialect tests, one an AEAT-grammar token `130-2026-1T-...` in a live discovery fixture, and the route gate names six more sites.

Those fixtures entered under `feat(cadrumo): land the in-flight source and packaging work` — another bare whole-index sweep. So the change has no attributable author: the sweeping agent did not write the fixtures, and the writing agent's identity is not in the history. The surface belongs to the tabular column-role mapping lane of the document-ingestion campaign, which is active and mid-flight, but that is an inference from surface ownership rather than an attribution.

This is the compounding form of the sweep hazard. Misattribution and a briefly-broken HEAD are recoverable within minutes. A red tree-wide gate with no recoverable owner persists, because the standing rule that a red full-tree gate needs an owner cannot be satisfied: there is nobody to route it to, and any agent who fixes it is patching another campaign's files to green a gate, which is separately forbidden.

**The two offender classes are not the same defect and must not be closed as one.** A bank export's filename containing a calendar quarter is external-world naming that the period grammar never parses; an AEAT-grammar token in a fixture is the thing the gate exists to catch. Whoever takes this must classify before allowlisting, and each allowlist entry must state its reason, or the allowlist becomes the honour-system list the gate was built to remove.

Recorded here rather than opened as a row in the owning campaign's plan, because that plan is mid-flight under other executors and inserting a row into a peer campaign's tracking document on an inference about ownership would create exactly the false attribution this document is about.
