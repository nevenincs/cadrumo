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

The instances fall into three classes with different fixes, and filing them together as "tools lie" would obscure that.

The first class misreports its own shape. The instrument is broken, degraded, or silently not doing the work, and says nothing about it. The mitigation is to check the shape rather than the exit code.

The second class reports truthfully about a frame narrower than the reliance placed on it. Nothing is misstated; the danger sits outside what the instrument was ever answering. The mitigation is to know each instrument's frame and to ask what it does not cover, which is not discoverable from a passing result.

The third class reports truthfully and completely, and is still unsafe to act on, because the subject is shared and moving, so a true answer has no shelf life. Here no check helps: verification and action cannot be made atomic against a subject other writers hold. The mitigation is to stop sharing the subject.

Only the first class is what "a tool lied" usually means, and it is the least dangerous of the three, because a broken instrument eventually produces an implausible answer. The second and third produce answers that stay plausible indefinitely.

The audit was written from the session that deleted the register-based censal pull. Two of the instances are that work's own defects rather than tooling, and they are included because they are the quietest members of the same class: values that passed every gate the project has.

## Findings

### truncated-semantic-index | critical | the code index self-reports success at a fraction of its content, so the mandatory discovery gate never refuses

The semantic search service reported `Source code sections: 221` against a tree of tens of thousands of files, while marking that generation `succeeded`. Later in the same session it read 466 and `running`. The standing discovery mandate requires refusing coding work when the service is DOWN, and the service was emphatically UP: it accepted queries and returned confident, well-formed, largely useless results. A truncated index is not a down service, so the refusal condition never fired, and the one probe run against it returned a single plausible file that could easily have been mistaken for a complete answer. The failure mode the mandate exists to prevent is adding a second implementation of something that already exists under a name nobody searched for; a partial index produces exactly the empty result that invites it.

### stale-linter-ignore-skips-every-contract | critical | import-linter aborted before evaluating and reported nothing

Recorded independently by another agent in the same session. Two `ignore_imports` entries named modules that no longer existed, one renamed and one removed, and import-linter aborts on a stale ignore before evaluating anything. Five layered architecture contracts had therefore not been checked at all, for as long as those entries had been stale. Restoring the run made real violations visible for the first time: three contracts kept, two broken. This is the purest form of the class. The gate passed by not running, and passing was indistinguishable from passing.

### schema-read-as-contract-honoured-as-prose | critical | the profile schema is authoritative to every reader and advisory to the code, in three places

Raised first as two escapes from one deleted surface, and promoted after a third instance made it a pattern rather than a slip.

The deleted censal pull wrote a profile fact at `censo.filed_on`, a path the user-profile schema does not declare, and stamped it with a provenance token absent from the schema's declared source enum. Both passed every gate the project has. `UserProfileFact.source` is a length-constrained string rather than the enum the schema declares, so the declared value set is documentation at that boundary and not a constraint, and nothing cross-checks a fact's path against the schema's declared field set. Neither escape was loud; they surfaced only because the surface produced no output at all, so no fact was ever built to write.

The provenance enum is not merely theoretically unenforced. The shipped censal-artefact path already stamps a token the declared enum does not list, so the closed set has a live violator independent of any deleted code.

The third instance is wider. The entire `auth` section is absent from the compiled profile-key catalogue: validating a profile map containing `auth.provider`, `auth.dni_nie`, `auth.numero_soporte` and `auth.fecha_validez` reports all four as unknown keys, while `censo.activity_start_date` in the same call is known. Verified directly rather than taken on report. So the schema declares a date-typed field that nothing enforces on the write path, and a malformed date is stored verbatim and typed into an AEAT form, where the authority refuses it opaquely. The operator meets a remote error for a value their own profile was supposed to have caught, which is the worst available place to discover it.

Three instances across two sections is not a slip. The schema is being read as a contract by everyone who writes against it and honoured as prose by the code that consumes it, and the gap is invisible precisely because the declarations look authoritative.

### commit-technique-leaves-armed-state-outside-its-frame | high | a low-level commit path succeeds truthfully and leaves the index primed to revert the work

Reported by the agent who hit it, against their own earlier recommendation of the technique.

Building a commit with `git commit-tree` followed by `update-ref` does not update the main index. The ref moves, the commit object is correct, the working tree is correct, and every check run afterwards passes. But the index still holds the pre-commit blob for every path just committed, so it now carries a reverse delta against the new HEAD. The next bare commit by any agent in the worktree silently reverts the work that was just landed. It was caught by a status check immediately afterwards, showing the committed paths still modified against the index.

The operation misreported nothing. It reported success about exactly what it did, and said nothing about the state it left behind, because that state was never in its frame. This is the second class in its sharpest form: the answer was true, complete, and dangerous in what it did not cover. The remedy is to stage the same paths immediately after the ref update, since the working tree already equals what was committed; with index-rewinding commands prohibited in this worktree, that add is the only available route.

The technique's own scope is the durable lesson. A main-index commit with an explicit pathspec is the default; the low-level path is the fallback for the one case where a pathspec commit would sweep a peer's working-tree changes into the commit. It was reached for out of habit on a commit where the ordinary route was available, and the heavier tool carried a hazard the lighter one does not have.

### replace-flag-mistaken-for-recursive | high | a search flag silently rewrote every match and exited zero

Several sweeps ran as `rg -rn`, in the belief that `-r` meant recursive. It means `--replace`, so ripgrep substituted the literal `n` for every match and exited zero. The output was well-formed and plausible: an AEAT launcher path read as `/wlpl/n/n` rather than `/wlpl/BUGC-JDIT/MdcAcceso`, and a symbol inventory rendered every symbol name as `n`. The corruption was caught only because one line looked implausible on its face, not because any check flagged it. A wrong explanation for the corruption was reported before the real cause was found, which is its own instance of the same problem: the first diagnosis was also plausible and also unverified.

### truncated-capture-makes-absence-meaningless | medium | an empty grep over a 12-line tail was nearly reported as a clean result

A vault check emitting 14721 warnings was captured to a background log that retained twelve tail lines. Grepping that log for the document under review returned nothing, and nothing is what a clean result also looks like. The absence proved only that the document was not among the last twelve lines. This was caught before it was reported, but the same pattern in the same session had already destroyed the diagnostic value of earlier captures, and the general form is that a negative result is evidence only once the search is known to have covered the subject.

### parity-check-mistaken-for-write-confirmation | medium | the scaffold check verbs prove agreement, not that an intended change landed

The second class in its mildest form. The documentation and locale scaffolding CLIs both offer a check mode that verifies the tree matches freshly generated output. That is a parity assertion, and a truthful one. It confirms that the generated surface agrees with its source; it does not confirm that any particular intended edit was made, and it returns clean on a tree where the intended change was never attempted. Reading it as write confirmation is a category error the verb's name invites. It is sound as a drift gate and silent as a landing gate, and nothing in a passing result distinguishes the two.

### true-answer-about-a-moved-subject | high | a clean pre-flight check was accurate and still unsafe to act on

This is the second class, and its only member here. Landing a change into a file held by another agent's uncommitted work used the project's prescribed staged-patch drive: build a patch against the committed copy, stage it without touching the working tree, verify the staged set, then commit. The pre-flight `--check` passed and was correct. Between that check and the commit, another agent staged eleven of their own files into the shared index, so committing the verified index would have swept their work under the wrong commit. The instrument did not malfunction and did not misreport itself. It answered truthfully about a state that had already changed by the time the answer was used, because the index is shared and every agent writes to it.

The drive's own verification step caught this, which is why nothing was committed and the staged hunks were reversed out with the exact inverse of the apply. But that step can only detect the collision after the fact. Making the apply, the verification and the commit a single uninterruptible step narrowed the window enough to land on retry, and narrowing is the most that can be done: no check can close it, because the subject does not stop moving while the check is read. The resolution is to give the change to the file's owner so the subject is not shared at all.

### brief-accurate-when-written-stale-on-arrival | low | coordination messages exhibit the same shape at the human layer

Several instructions in this session were correct when composed and superseded by the time they arrived, because the tree moved in between. Work was assigned that had already landed, an ordering was designed against a state that no longer existed, and a hand-off was briefed around deletions already absent from the committed tree. No message was wrong when sent. This is the same failure as the class above, with the same cause and the same non-fix: the sender verified a state, and the state was shared and moving. It is recorded because it produced real rework, and because the mitigation is identical, namely confirming current state at the moment of acting rather than trusting the most recent report of it.

## Recommendations

Treat exit code as the weakest available signal. For every gate the project relies on, identify what its output should look like when it is genuinely working, and check that shape. The semantic index should be checked for a section count consistent with the tree, not merely for a live service; the discovery mandate's refusal condition should be widened from service-down to service-not-usefully-indexed, since the current wording cannot see the failure that actually occurred.

Make silently-skipped work impossible to confuse with passed work. The import-linter case is the strongest argument for auditing every gate that can abort or no-op before evaluating, and for asserting that each ran over a non-empty subject. A gate that cannot distinguish nothing-to-check from everything-checked is not a gate.

Settle what the profile schema IS. With three instances across two sections, the question is no longer whether one enum should be enforced; it is whether the schema is a contract or a description, because it is currently read as the former and honoured as the latter. A follow-on decision record should state which, and the code should then match it: either the declared field set, types and closed value sets become constraints enforced at the fact-write boundary, or they are explicitly documentation and the real validation is named and located. Either answer is defensible and the present ambiguity is not, because it makes every declaration look load-bearing while some are inert. Whichever is chosen, the shipped provenance-token violation and the unenrolled `auth` section are existing breaches to reconcile rather than new work, and a gate asserting that every schema-declared section appears in the compiled key catalogue would have caught the second mechanically; it was found instead by a person trying a value by hand.

Know each instrument's frame, and write the frame down wherever the instrument is recommended. The second class cannot be caught by running anything. It is caught by knowing in advance that a parity check does not confirm a write and that a low-level commit does not touch the index. Both the staged-patch drive and the low-level commit path earned their place as fallbacks for one specific hazard, and both were reached for out of habit in situations where the ordinary route was available and safer. A recommended technique should carry its scope and its blind spot, or familiarity promotes it to the default and it brings its own hazards to cases that never needed them.

Prefer ownership transfer over window narrowing for shared-subject work. The staged-patch drive is correct and should remain the technique for landing into a file another agent holds, but this session showed its verification step is a detector rather than a guarantee. Where the file has an active owner who is about to edit the same region, handing them the change removes the race instead of scheduling around it, and that is a resolution rather than a workaround. Where no owner is available, the apply, the verification and the commit should be one uninterruptible operation.

Re-verify state at the moment of acting. This applies to agents reading a peer's report and to whoever is coordinating them. A report is a description of a past state, and in this worktree the interval between a report and a decision made on it is routinely long enough for the decision to be wrong. The cheap discipline is a state check immediately before acting, not immediately before deciding.
