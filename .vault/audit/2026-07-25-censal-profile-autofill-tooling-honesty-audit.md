---
tags:
  - '#audit'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
related: []
---

# `censal-profile-autofill` audit: `tooling honesty`

## Scope

A single session's worth of instruments that ran, exited zero, and were wrong. None of these was found by asking whether a command failed, because none of them failed. They were found by asking whether the answer had the shape the answer should have had.

The instances fall into two classes with different fixes, and filing them together as "tools lie" would obscure that. The first class misreports its own shape: the instrument is broken, degraded, or silently not doing the work, and says nothing about it. The second class reports correctly and is still unsafe to act on, because the subject is shared and moving, so a true answer has no shelf life. For the first class the mitigation is to check the shape rather than the exit code. For the second no check helps, because verification and action cannot be made atomic against a subject other writers hold; the mitigation is to stop sharing the subject.

The audit was written from the session that deleted the register-based censal pull. Two of the instances are that work's own defects rather than tooling, and they are included because they are the quietest members of the same class: values that passed every gate the project has.

## Findings

### truncated-semantic-index | critical | the code index self-reports success at a fraction of its content, so the mandatory discovery gate never refuses

The semantic search service reported `Source code sections: 221` against a tree of tens of thousands of files, while marking that generation `succeeded`. Later in the same session it read 466 and `running`. The standing discovery mandate requires refusing coding work when the service is DOWN, and the service was emphatically UP: it accepted queries and returned confident, well-formed, largely useless results. A truncated index is not a down service, so the refusal condition never fired, and the one probe run against it returned a single plausible file that could easily have been mistaken for a complete answer. The failure mode the mandate exists to prevent is adding a second implementation of something that already exists under a name nobody searched for; a partial index produces exactly the empty result that invites it.

### stale-linter-ignore-skips-every-contract | critical | import-linter aborted before evaluating and reported nothing

Recorded independently by another agent in the same session. Two `ignore_imports` entries named modules that no longer existed, one renamed and one removed, and import-linter aborts on a stale ignore before evaluating anything. Five layered architecture contracts had therefore not been checked at all, for as long as those entries had been stale. Restoring the run made real violations visible for the first time: three contracts kept, two broken. This is the purest form of the class. The gate passed by not running, and passing was indistinguishable from passing.

### undeclared-fact-path-and-provenance-token | high | two values reached a persistence boundary that no gate constrains

The deleted censal pull wrote a profile fact at `censo.filed_on`, a path the user-profile schema does not declare, and stamped it with a provenance token absent from the schema's declared source enum. Both passed every gate the project has. `UserProfileFact.source` is a length-constrained string rather than the enum the schema declares, so the declared value set is documentation at that boundary and not a constraint, and nothing cross-checks a fact's path against the schema's declared field set. Neither escape was loud. They surfaced only because the surface produced no output at all, so no fact was ever built to write; had the read worked, both would have landed silently. This holds for every writer of a profile fact and is independent of the censal decision.

### replace-flag-mistaken-for-recursive | high | a search flag silently rewrote every match and exited zero

Several sweeps ran as `rg -rn`, in the belief that `-r` meant recursive. It means `--replace`, so ripgrep substituted the literal `n` for every match and exited zero. The output was well-formed and plausible: an AEAT launcher path read as `/wlpl/n/n` rather than `/wlpl/BUGC-JDIT/MdcAcceso`, and a symbol inventory rendered every symbol name as `n`. The corruption was caught only because one line looked implausible on its face, not because any check flagged it. A wrong explanation for the corruption was reported before the real cause was found, which is its own instance of the same problem: the first diagnosis was also plausible and also unverified.

### truncated-capture-makes-absence-meaningless | medium | an empty grep over a 12-line tail was nearly reported as a clean result

A vault check emitting 14721 warnings was captured to a background log that retained twelve tail lines. Grepping that log for the document under review returned nothing, and nothing is what a clean result also looks like. The absence proved only that the document was not among the last twelve lines. This was caught before it was reported, but the same pattern in the same session had already destroyed the diagnostic value of earlier captures, and the general form is that a negative result is evidence only once the search is known to have covered the subject.

### parity-check-mistaken-for-write-confirmation | medium | the scaffold check verbs prove agreement, not that an intended change landed

The documentation and locale scaffolding CLIs both offer a check mode that verifies the tree matches freshly generated output. That is a parity assertion. It confirms that the generated surface agrees with its source; it does not confirm that any particular intended edit was made, and it returns clean on a tree where the intended change was never attempted. Reading it as write confirmation is a category error the verb's name invites, and it is only safe as a drift gate.

### true-answer-about-a-moved-subject | high | a clean pre-flight check was accurate and still unsafe to act on

This is the second class, and its only member here. Landing a change into a file held by another agent's uncommitted work used the project's prescribed staged-patch drive: build a patch against the committed copy, stage it without touching the working tree, verify the staged set, then commit. The pre-flight `--check` passed and was correct. Between that check and the commit, another agent staged eleven of their own files into the shared index, so committing the verified index would have swept their work under the wrong commit. The instrument did not malfunction and did not misreport itself. It answered truthfully about a state that had already changed by the time the answer was used, because the index is shared and every agent writes to it.

The drive's own verification step caught this, which is why nothing was committed and the staged hunks were reversed out with the exact inverse of the apply. But that step can only detect the collision after the fact. Making the apply, the verification and the commit a single uninterruptible step narrowed the window enough to land on retry, and narrowing is the most that can be done: no check can close it, because the subject does not stop moving while the check is read. The resolution is to give the change to the file's owner so the subject is not shared at all.

### brief-accurate-when-written-stale-on-arrival | low | coordination messages exhibit the same shape at the human layer

Several instructions in this session were correct when composed and superseded by the time they arrived, because the tree moved in between. Work was assigned that had already landed, an ordering was designed against a state that no longer existed, and a hand-off was briefed around deletions already absent from the committed tree. No message was wrong when sent. This is the same failure as the class above, with the same cause and the same non-fix: the sender verified a state, and the state was shared and moving. It is recorded because it produced real rework, and because the mitigation is identical, namely confirming current state at the moment of acting rather than trusting the most recent report of it.

## Recommendations

Treat exit code as the weakest available signal. For every gate the project relies on, identify what its output should look like when it is genuinely working, and check that shape. The semantic index should be checked for a section count consistent with the tree, not merely for a live service; the discovery mandate's refusal condition should be widened from service-down to service-not-usefully-indexed, since the current wording cannot see the failure that actually occurred.

Make silently-skipped work impossible to confuse with passed work. The import-linter case is the strongest argument for auditing every gate that can abort or no-op before evaluating, and for asserting that each ran over a non-empty subject. A gate that cannot distinguish nothing-to-check from everything-checked is not a gate.

Close the profile-fact boundary. This needs a decision recorded in its own right rather than an implementation choice made in passing: whether the schema's declared provenance enum and declared field set become constraints enforced at the fact boundary, or whether they remain documentation with validation living elsewhere. Either answer is defensible; the current state, where they read as constraints and behave as prose, is not. A follow-on decision record should settle it, and it applies to every writer of a profile fact regardless of the censal outcome.

Prefer ownership transfer over window narrowing for shared-subject work. The staged-patch drive is correct and should remain the technique for landing into a file another agent holds, but this session showed its verification step is a detector rather than a guarantee. Where the file has an active owner who is about to edit the same region, handing them the change removes the race instead of scheduling around it, and that is a resolution rather than a workaround. Where no owner is available, the apply, the verification and the commit should be one uninterruptible operation.

Re-verify state at the moment of acting. This applies to agents reading a peer's report and to whoever is coordinating them. A report is a description of a past state, and in this worktree the interval between a report and a decision made on it is routinely long enough for the decision to be wrong. The cheap discipline is a state check immediately before acting, not immediately before deciding.
