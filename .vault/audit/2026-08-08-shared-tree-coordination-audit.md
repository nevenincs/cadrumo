---
tags:
  - '#audit'
  - '#shared-tree-coordination'
date: '2026-08-08'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:497daa949a6372c2efd89feaaf5a4d8ee7d0c4f868b1e810a29a8835b6897881'
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

A second, independently reported instance: the whole-vault `check all --fix` dirtied vault documents belonging to two other features across two runs. Same shape, same correct response — commit only your own paths by explicit pathspec and revert nothing. The reporting executor switched to the narrower `check placeholders`, which is the right mitigation.

**One claim in this class was reported and then withdrawn by its own author, and the withdrawal is recorded rather than the claim quietly dropped.** A third verb, the modified-stamp check, was reported as writing even without `--fix`. Its author retested and found it reports only: their file stayed flagged after the run and needed a round-trip through the owning edit verb to re-attest. So whatever re-stamped two execution records in another feature earlier, it was not that verb, and the likeliest explanation is an ordinary peer edit. Recorded because a withdrawn finding left unrecorded gets re-derived by the next reader, and because the withdrawal itself is the useful part: the author distinguished "my file changed after I ran X" from "X changed my file", which are not the same observation.

The `--feature` scoping advice survives the withdrawal on its own merits, since two verbs in this class do write tree-wide.

**The withdrawal above was itself too broad, and the corrected position is narrower than either the original claim or its retraction.** The re-stamping phenomenon is real and reproducible: six execution records across two features now sit dirty with body-hash-only changes, bodies byte-identical to their committed versions. What remains unsupported is attributing it to the modified-stamp check specifically, since that verb demonstrably only reports — its own author's file stayed flagged after running it and needed a round-trip through the owning edit verb to re-attest.

So some feature-scoped vault verb re-stamps the feature's sibling documents, and which one has not been isolated. The operative caution is therefore about the class rather than the member: **treat any feature-scoped vault verb as potentially re-stamping the other documents in that feature.** Leaving the affected records dirty and untouched for their owners remains the right response, exactly as with the tree-wide case.

This correction is recorded rather than folded into the paragraph above because the sequence matters. A claim was made, retracted on evidence, and then partially reinstated on better evidence — and a reader who sees only the final position cannot tell which parts were measured and which inferred. The measured facts are the six records and the reporting-only behaviour of the one verb tested; the unmeasured part is which verb is responsible.

### Why this is recorded rather than codified

The standing worktree-safety rule already forbids the destructive verbs and already prescribes the explicit-pathspec commit and the apply-cached drive. Nothing here contradicts it. What these occurrences add is the observation that **following the rule is not sufficient protection when a peer does not**, and that the resulting damage lands on the compliant agent. That is a coordination fact about this tree at this moment, not a new mandate, and the always-on rule corpus is already load-bearing on every session.

### Consequence observed: a red tree-wide gate whose owner is unrecoverable

The combined-period-string gate and the AEAT-route-literal centralisation gate are both red, and have been for the whole session. The combined-period gate names fourteen offending lines, twelve of them bank-statement fixture filenames of the shape `bank_bbva_2026Q1.csv` across the financial tabular providers and the core tabular-dialect tests, one an AEAT-grammar token `130-2026-1T-...` in a live discovery fixture, and the route gate names six more sites.

Those fixtures entered under `feat(cadrumo): land the in-flight source and packaging work` — another bare whole-index sweep. So the change has no attributable author: the sweeping agent did not write the fixtures, and the writing agent's identity is not in the history. The surface belongs to the tabular column-role mapping lane of the document-ingestion campaign, which is active and mid-flight, but that is an inference from surface ownership rather than an attribution.

This is the compounding form of the sweep hazard. Misattribution and a briefly-broken HEAD are recoverable within minutes. A red tree-wide gate with no recoverable owner persists, because the standing rule that a red full-tree gate needs an owner cannot be satisfied: there is nobody to route it to, and any agent who fixes it is patching another campaign's files to green a gate, which is separately forbidden.

**The two offender classes are not the same defect and must not be closed as one.** A bank export's filename containing a calendar quarter is external-world naming that the period grammar never parses; an AEAT-grammar token in a fixture is the thing the gate exists to catch. Whoever takes this must classify before allowlisting, and each allowlist entry must state its reason, or the allowlist becomes the honour-system list the gate was built to remove.

Recorded here rather than opened as a row in the owning campaign's plan, because that plan is mid-flight under other executors and inserting a row into a peer campaign's tracking document on an inference about ownership would create exactly the false attribution this document is about.

### A frozen `.git/index.lock` blocks every commit in the tree, and the sanctioned response is to queue

Observed continuously across a multi-hour window: `.git/index.lock` present, zero bytes, mtime frozen at `2026-08-08 19:29:59`, while the last commit in the tree landed at `19:25:51`. Every `git commit` in the worktree fails with `fatal: Unable to create '.../.git/index.lock': File exists`, including a correctly-formed explicit-pathspec commit touching only its author's own clean files.

The diagnosis rule works and should be applied before anything else: an **advancing** mtime means contention and will clear on its own; a **frozen** mtime means the holder died. This one is frozen, four minutes after the last successful commit, which is the signature of a git process that crashed mid-commit rather than one still working.

Git's own error text ends with `remove the file manually to continue`. **That instruction is forbidden here and must not be followed.** The prohibition on deleting anything under `.git/` — `index.lock` named explicitly — has no debugging exception, and the tool suggesting it does not create one. A lock whose holder is genuinely dead is indistinguishable, from inside a single agent's view, from one held by a peer's long-running operation that is about to write; `ps -W` cannot prove absence of the holder, so "the holder is dead" is never a conclusion an agent can reach with certainty, only a reading of the mtime.

**What follows for a blocked author.** The lock blocks publication, not work. Do the research, land the edits in the working tree, run the real gates, and prove the change with a mutation pass — all of that completes normally with the lock held. Then record the change as a queued diff naming every file, and hand the queue forward rather than stalling the iteration. What must not happen is abandoning verification because the commit cannot land: an unverified queued diff is strictly worse than a verified one, because the next agent to pick it up inherits a change nobody has proven.

The cost is real and worth stating plainly. Queued work sits in the working tree as uncommitted changes indistinguishable from any other peer's WIP, which means it is exposed to exactly the bare whole-index sweep this document opens with — a sweep would publish it under someone else's subject. The two hazards compound: the lock forces work to accumulate uncommitted, and accumulated uncommitted work is what the sweep hazard feeds on. That argues for keeping each queued change small and independently committable, so that whichever of them a sweep captures, the rest still land cleanly under their own author.

**Second independent confirmation, ~5h51m into the freeze.** Re-observed at `2026-08-09 01:20`: same zero-byte file, same frozen `2026-08-08 19:29:59` mtime, unchanged across the whole of a second remediation iteration. The queue-and-continue response held up: a full research-implement-test-mutation-prove cycle completed normally with the lock held, and only publication was blocked. The frozen mtime remains the diagnosis, and the file remains untouched.

One refinement worth recording for whoever picks this up. A blocked iteration still needs to compare a working-tree change against its committed baseline, and the sanctioned procedure for that — copy the working file aside, write the HEAD bytes in place, test, restore — opens a mutation window that a bare whole-index sweep could otherwise publish. **While the lock is frozen that window is actually safe, because no agent in the tree can commit anything at all.** The lock that blocks your publication also blocks the sweep that would capture your window. That is a genuine, if narrow, compensation, and it makes the HEAD-bytes comparison the cheapest reliable way to separate a pre-existing red test from one your own edit caused. Restore from the scratch copy and verify byte-identical by hash afterwards regardless; the safety is situational and evaporates the moment the lock clears.

### A numstat proves your change LANDED, not that it was the ONLY thing that landed

A fresh instance of this document's opening hazard, from the compliant side, and it defeated the verification this document itself prescribes.

An agent committed an ADR amendment with an explicit pathspec, believing that scoped the commit to its own edit. It scopes to the **file**. A peer had two decisions sitting uncommitted in the same document, and the pathspec commit published all of it — three paragraphs the committing agent did not write, under a subject line about something else. `git log` now attributes two of the peer's decisions to the wrong author.

**The verify-after check ran, and passed, and could not have caught it.** The agent had been running `git show <sha> --numstat` after every commit all session, exactly as prescribed above, and did so here: 62 insertions, 2 deletions. That number is real and correct. It simply cannot distinguish 55 lines of the author's own work from 7 lines of someone else's.

The two claims are different and the numstat only establishes the first:

- **"my intended change landed"** — what a numstat total shows
- **"ONLY my intended change landed"** — what a shared-document commit actually needs

On a file one agent is editing the two coincide, which is why the habit reads as sufficient for months before it fails. On a contended document they diverge silently, and the failure is invisible in exactly the artefact used to check it.

**What would have caught it:** reading the diff's added lines rather than their count — `git show <sha> -- <path> | rg '^\+'` and confirming the content is yours. On a document, that is cheap. The apply-cached drive already prescribed above is the stronger answer when a file is known to be contended; the gap here was that the agent never re-classified the document as contended, despite having read plan rows hours earlier that explicitly targeted the same file.

**The remedy is the record, not a git operation.** History was not rewritten. The misattribution is stated in the campaign's own record so the peer's authorship survives where `git log` no longer carries it — the same response this document already prescribes for a sweep, applied by the agent that caused one rather than the agent that suffered it.

### A documented rationale that reads as a smell can be load-bearing, and the cheap check is to run it

A prior remediation pass nominated four sites for re-typing: `expression` fields declared `dict[str, object]` on CLI payload schemas, where a real `FormulaExpression` model already exists in the registry package. The pattern matches the standing prohibition on bare mappings at typed boundaries almost exactly, and the nomination read as obviously correct.

It is wrong, and the module already says so. The payload module's own docstring states that the `expression` fields stay `dict[str, object]` because `FormulaExpression` is a recursive tree, and that the strict `OutputSchema` base does not coerce lists back to tuples on re-validation.

That is not a rationalisation. `FormulaExpression` declares `args: tuple[FormulaExpression, ...]` and inherits a strict model config, so a round-trip through `model_dump(mode="json")` renders the tuple as a JSON array and re-validation refuses it: `Input should be a valid tuple ... input_type=list`. The refusal reproduces in four lines against the real classes, with no test harness. Re-typing the four sites would have made every one of those payloads unre-validatable.

**What follows.** The prohibition on untyped boundary mappings has a real exception where a strict recursive model meets a JSON transport, and this is it. The available remedies are each worse than the documented status quo: a parallel list-shaped projection of `FormulaExpression` would be a second definition of one concept, and relaxing strictness on `OutputSchema` would weaken the contract for every payload in the tree to type one field. The `dict[str, object]` is the deliberate escape hatch, and it is already documented at the site.

The transferable part is procedural. A rule-shaped violation that has a rationale written beside it is not thereby cleared — prose asserting a property the code lacks is a known failure mode, and the rationale deserves testing rather than deference. But it deserves *testing*, not dismissal: the check here cost four lines and inverted the conclusion. Running it is cheaper than either believing the docstring or overriding it, and a nomination inherited from an earlier pass carries no more authority than the docstring it contradicts. Both are claims; only one of them was measured.
