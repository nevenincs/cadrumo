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

The fourth class is truthful, complete, timely, and structurally unable to act. The check runs, is correct, and is positioned where its answer cannot stop what it is guarding. The mitigation is positional rather than analytical: the check must sit where a failure halts the operation.

Only the first class is what "a tool lied" usually means, and it is the least dangerous of the four, because a broken instrument eventually produces an implausible answer. The other three produce answers that stay plausible indefinitely.

The audit was written from the session that deleted the register-based censal pull. Two of the instances are that work's own defects rather than tooling, and they are included because they are the quietest members of the same class: values that passed every gate the project has.

## Findings

### truncated-semantic-index | critical | the code index self-reports success at a fraction of its content, so the mandatory discovery gate never refuses

The semantic search service reported `Source code sections: 221` against a tree of tens of thousands of files, while marking that generation `succeeded`. Later in the same session it read 466 and `running`. The standing discovery mandate requires refusing coding work when the service is DOWN, and the service was emphatically UP: it accepted queries and returned confident, well-formed, largely useless results. A truncated index is not a down service, so the refusal condition never fired, and the one probe run against it returned a single plausible file that could easily have been mistaken for a complete answer. The failure mode the mandate exists to prevent is adding a second implementation of something that already exists under a name nobody searched for; a partial index produces exactly the empty result that invites it.

### stale-linter-ignore-skips-every-contract | critical | import-linter aborted before evaluating and reported nothing

Recorded independently by another agent in the same session. Two `ignore_imports` entries named modules that no longer existed, one renamed and one removed, and import-linter aborts on a stale ignore before evaluating anything. Five layered architecture contracts had therefore not been checked at all, for as long as those entries had been stale. Restoring the run made real violations visible for the first time: three contracts kept, two broken. This is the purest form of the class. The gate passed by not running, and passing was indistinguishable from passing.

### schema-read-as-contract-honoured-as-prose | high | two values reached a persistence boundary the schema was assumed to constrain

Downgraded from critical, and narrowed from three instances to two. The correction is recorded below rather than edited away, because how the third instance was produced is more instructive than the instance was.

The deleted censal pull wrote a profile fact at `censo.filed_on`, a path the user-profile schema does not declare, and stamped it with a provenance token absent from the schema's declared source enum. Both passed every gate the project has. `UserProfileFact.source` is a length-constrained string rather than the enum the schema declares, so that declared value set binds nothing, and nothing cross-checks a fact's path against the schema's declared field set. Neither escape was loud; they surfaced only because the surface produced no output at all, so no fact was ever built to write.

The provenance enum is not merely theoretically unenforced. The shipped censal-artefact path already stamps a token the declared enum does not list, so the closed set has a live violator independent of any deleted code. The path escape remains unclosed.

A third instance was claimed and is WITHDRAWN. It held that the entire `auth` section was missing from the compiled profile-key catalogue, so a schema-declared `date` type was enforced nowhere and a malformed date would be refused opaquely by AEAT rather than by the profile. A five-line probe against the real store disproved it: the write path enforces the date type, refusing `not-a-date`, `15/03/2030`, `2030-13-45` and `20300101` while accepting `2030-01-01`, on both the register and update paths. The catalogue in question is the wizard completeness checker - which keys the setup interview asks for - and not a type validator, so "unknown key" there means "not part of the interview". Its unknown-key output has no production consumer. The section's absence from it is correct by design, and the parity gate proposed as the remedy would have frozen a correct design as a defect.

The withdrawal cost nothing because it was caught, but it was produced by the author of this record and shipped here as verified. The reasoning was: run the function, observe the four keys returned as unknown, report it as directly verified rather than taken on report.

The precise location of the failure is worth stating, because "I overclaimed" is too coarse to be useful to anyone. The value WAS verified, accurately: the function really does return those four keys as unknown, and re-running it today gives the same answer. The unverified step was the SEMANTICS - what that return value means - and it was invisible because the function's name supplied an answer before the question was asked. So "verified" is not the overclaim. The overclaim is that verifying a value verifies its meaning. That distinction matters because the next person will also verify something real and infer something adjacent to it, and will feel, correctly, that they checked. A catalogue named like a validator, holding a field named like a gap, supplies the adjacent inference for free.

Two readers made the same move: the finding was reported on a name, and accepted into a decision record without anyone asking what that function validates.

The two surviving instances are of a different kind, and the difference is the durable lesson. They are escapes that HAPPENED: a path was written, a token was stamped, and the artefacts exist. The withdrawn one was an inference from structure about what could not be enforced. Observed escapes held under probing; the inferred gap did not.

### commit-technique-leaves-armed-state-outside-its-frame | high | a low-level commit path succeeds truthfully and leaves the index primed to revert the work

Reported by the agent who hit it, against their own earlier recommendation of the technique.

Building a commit with `git commit-tree` followed by `update-ref` does not update the main index. The ref moves, the commit object is correct, the working tree is correct, and every check run afterwards passes. But the index still holds the pre-commit blob for every path just committed, so it now carries a reverse delta against the new HEAD. The next bare commit by any agent in the worktree silently reverts the work that was just landed. It was caught by a status check immediately afterwards, showing the committed paths still modified against the index.

The operation misreported nothing. It reported success about exactly what it did, and said nothing about the state it left behind, because that state was never in its frame. This is the second class in its sharpest form: the answer was true, complete, and dangerous in what it did not cover. The remedy is to stage the same paths immediately after the ref update, since the working tree already equals what was committed; with index-rewinding commands prohibited in this worktree, that add is the only available route.

The technique's own scope is the durable lesson. A main-index commit with an explicit pathspec is the default; the low-level path is the fallback for the one case where a pathspec commit would sweep a peer's working-tree changes into the commit. It was reached for out of habit on a commit where the ordinary route was available, and the heavier tool carried a hazard the lighter one does not have.

### replace-flag-mistaken-for-recursive | high | a search flag silently rewrote every match and exited zero

Several sweeps ran as `rg -rn`, in the belief that `-r` meant recursive. It means `--replace`, so ripgrep substituted the literal `n` for every match and exited zero. The output was well-formed and plausible: an AEAT launcher path read as `/wlpl/n/n` rather than `/wlpl/BUGC-JDIT/MdcAcceso`, and a symbol inventory rendered every symbol name as `n`. The corruption was caught only because one line looked implausible on its face, not because any check flagged it. A wrong explanation for the corruption was reported before the real cause was found, which is its own instance of the same problem: the first diagnosis was also plausible and also unverified.

### truncated-capture-makes-absence-meaningless | medium | an empty grep over a 12-line tail was nearly reported as a clean result

A vault check emitting 14721 warnings was captured to a background log that retained twelve tail lines. Grepping that log for the document under review returned nothing, and nothing is what a clean result also looks like. The absence proved only that the document was not among the last twelve lines. This was caught before it was reported, but the same pattern in the same session had already destroyed the diagnostic value of earlier captures, and the general form is that a negative result is evidence only once the search is known to have covered the subject.

### gate-whose-fixture-embeds-what-it-forbids | high | three tests contained the defect they guarded against, and none could see it

The second class at its most consequential, because the instrument here is a GATE - the thing relied on to catch exactly this.

Three instances surfaced in one session, from three independent authors, while removing pinned load-balancer hosts from live readers. A test asserting a captured URL against a numbered host. A fixture asserting a source URL on a host that a live probe had already shown returns 404 for that route. And a centralisation test asserting that each exported URL equalled a build against one numbered host - a pinned host inside the test whose stated purpose was proving those routes are centralised. That last one would have REFUSED a correctly de-pinned URL, so the defect could not be fixed without its own guard failing.

None of the three was visible to the gates around them, and the reason generalises well past hosts: a behavioural gate cannot see a pin, because the pin is in the FIXTURE, and the fixture is what the gate trusts. The gate is truthful about what it measures. What it measures simply does not include the values it was handed. So the danger sits outside the frame, and no amount of running it helps - it is green by construction and would stay green while the property it names quietly stopped holding.

A fourth instance was caught before commit and belongs in the count, because it shows how little the awareness protects: the author of one of the fixes wrote four literal hosts into a new gate whose subject was literal hosts, hours after writing this audit's finding about names not being evidence. Knowing the pattern does not stop it. Only reading the source does.

The general form: any gate whose fixture embeds an instance of what the gate forbids is green by construction, and the only instrument that sees it is a scan of the source rather than a run of the behaviour.

### parity-check-mistaken-for-write-confirmation | medium | the scaffold check verbs prove agreement, not that an intended change landed

The second class in its mildest form. The documentation and locale scaffolding CLIs both offer a check mode that verifies the tree matches freshly generated output. That is a parity assertion, and a truthful one. It confirms that the generated surface agrees with its source; it does not confirm that any particular intended edit was made, and it returns clean on a tree where the intended change was never attempted. Reading it as write confirmation is a category error the verb's name invites. It is sound as a drift gate and silent as a landing gate, and nothing in a passing result distinguishes the two.

### true-answer-about-a-moved-subject | high | a clean pre-flight check was accurate and still unsafe to act on

This is the second class, and its only member here. Landing a change into a file held by another agent's uncommitted work used the project's prescribed staged-patch drive: build a patch against the committed copy, stage it without touching the working tree, verify the staged set, then commit. The pre-flight `--check` passed and was correct. Between that check and the commit, another agent staged eleven of their own files into the shared index, so committing the verified index would have swept their work under the wrong commit. The instrument did not malfunction and did not misreport itself. It answered truthfully about a state that had already changed by the time the answer was used, because the index is shared and every agent writes to it.

The drive's own verification step caught this, which is why nothing was committed and the staged hunks were reversed out with the exact inverse of the apply. But that step can only detect the collision after the fact. Making the apply, the verification and the commit a single uninterruptible step narrowed the window enough to land on retry, and narrowing is the most that can be done: no check can close it, because the subject does not stop moving while the check is read. The resolution is to give the change to the file's owner so the subject is not shared at all.

### verification-positioned-where-it-cannot-refuse | high | a correct check printed alongside the action it guards is decoration

The fourth class, and the only one whose fix is purely positional.

Committing into a worktree where other agents stage concurrently requires confirming the index holds nothing foreign. That confirmation was written into the same shell invocation as the staging and the commit, printing the foreign-file list immediately before proceeding. It ran, it was correct, and it listed six files belonging to another agent - and the commit went ahead anyway, because a printed list is output and nothing was reading it. The commit was saved only by carrying an explicit pathspec, which scoped it to the intended files regardless. Safety came from the instrument, not from the check.

The rule this yields is short enough to keep:

  A verification printed in the same breath as the action it guards is
  decoration. It has to be able to stop the action, which means it cannot
  be a line above it in the same command.

It generalises well past version control. A gate that runs after the write it validates, a check mode whose exit code nothing branches on, an assertion inside a block that has already committed its effect, and a report emitted alongside rather than before the decision are all the same defect: the finding is correct and arrives with no authority to refuse. This is distinct from the first class because nothing is misreported, from the second because the frame is right, and from the third because the answer is current. The check is simply in the wrong place to matter.

A second instance from the same session shows the class does not need a check to be present at all - only a stopping mechanism that turns out to be incidental. A commit message containing inner double quotes broke the surrounding shell quoting, and fragments of the prose were passed to the commit as pathspecs. It failed, loudly, and nothing was committed. But it failed only because git rejected those fragments as paths that do not exist. Had any fragment happened to match a real path, the result would have been an arbitrary subset of files committed under a truncated message, reported as success. What stopped it was a coincidence of vocabulary, not a guard. The fix is a uniquely-named message file for anything carrying prose, uniquely-named for two reasons: the scratchpad is shared between agents, so a conventional name is also a collision risk.

The repair is mechanical. Where a check must gate an action, the two belong in one construct in which failure halts - a conditional that aborts, a fixture that raises, a gate that runs before the write - and never in sequence with the operator expected to read between them. The same session later did it correctly, making apply, verification and commit a single step that reverses its own staging and exits on any foreign hunk, which is what a check with authority looks like.

### brief-accurate-when-written-stale-on-arrival | low | coordination messages exhibit the same shape at the human layer

Several instructions in this session were correct when composed and superseded by the time they arrived, because the tree moved in between. Work was assigned that had already landed, an ordering was designed against a state that no longer existed, and a hand-off was briefed around deletions already absent from the committed tree. No message was wrong when sent. This is the same failure as the class above, with the same cause and the same non-fix: the sender verified a state, and the state was shared and moving. It is recorded because it produced real rework, and because the mitigation is identical, namely confirming current state at the moment of acting rather than trusting the most recent report of it.

## Recommendations

Treat exit code as the weakest available signal. For every gate the project relies on, identify what its output should look like when it is genuinely working, and check that shape. The semantic index should be checked for a section count consistent with the tree, not merely for a live service; the discovery mandate's refusal condition should be widened from service-down to service-not-usefully-indexed, since the current wording cannot see the failure that actually occurred.

Make silently-skipped work impossible to confuse with passed work. The import-linter case is the strongest argument for auditing every gate that can abort or no-op before evaluating, and for asserting that each ran over a non-empty subject. A gate that cannot distinguish nothing-to-check from everything-checked is not a gate.

Settle what the profile schema IS. Two observed escapes at one boundary put the question past whether a single enum should be enforced; it is whether the schema is a contract or a description, because it is currently read as the former and honoured as the latter. A follow-on decision record should state which, and the code should then match it: either the declared field set, types and closed value sets become constraints enforced at the fact-write boundary, or they are explicitly documentation and the real validation is named and located. Either answer is defensible and the present ambiguity is not, because it makes every declaration look load-bearing while some are inert. Whichever is chosen, the shipped provenance-token violation and the unenrolled `auth` section are existing breaches to reconcile rather than new work, and a gate asserting that every schema-declared section appears in the compiled key catalogue would have caught the second mechanically; it was found instead by a person trying a value by hand.

Scan the source for any property a behavioural gate cannot observe. Where a gate forbids something that can appear in its own fixtures - a pinned host, a hardcoded credential, a literal that should come from a registry - the behavioural half is structurally blind to it, and the only instrument that sees it is a source scan. Three tests in one session contained the defect they guarded, from three authors, and a fourth was caught mid-write by an author who had that very morning written down why names are not evidence. So the scan is not a backstop for careless people; it is the only thing in the class that can fail. Where such a scan cannot pass yet because the property is half-fixed, say so in the test that would carry it rather than omitting it silently: a gate that cannot pass teaches nobody anything, but an absent gate nobody can explain teaches less.

Know each instrument's frame, and write the frame down wherever the instrument is recommended. The second class cannot be caught by running anything. It is caught by knowing in advance that a parity check does not confirm a write and that a low-level commit does not touch the index. Both the staged-patch drive and the low-level commit path earned their place as fallbacks for one specific hazard, and both were reached for out of habit in situations where the ordinary route was available and safer. A recommended technique should carry its scope and its blind spot, or familiarity promotes it to the default and it brings its own hazards to cases that never needed them.

Name the ref you measured, and mean it. This is a separate axis from staleness above, and folding the two together would blunt both: a stale measurement was true of the right subject at the wrong time, while this one is true of the wrong subject entirely, and re-running sooner does not fix it. In a worktree several agents write into, the working tree and the committed content are routinely different, and a test run measures the tree. Reporting a tree result as a HEAD result inverts what it means. A failure in the tree over a clean commit is an unlanded change's fallout with a known owner; the same failure at the commit is everyone's emergency. Same red, opposite responses.

Two instances a few minutes apart make the case better than either alone, because they point in opposite directions. One reported four failures as live at the commit; they came from a peer's uncommitted enforcement, and at the commit those tests passed - a false red. The other ran a suite after a peer reported a regression, saw it pass, and could reasonably have declared the report false - a false green from the identical cause. Neither run was wrong about what it measured; both were wrong about what they had measured.

The discriminator is one command and belongs beside predicting a count before re-running: when a test fails, retrieve from the commit the file you believe is responsible and check whether the mechanism is even present. If the constraint that raises the failure does not exist there, a working tree has been measured. The habit that fails here is the one that feels most diligent - the failure carried an obvious cause, and an obvious cause suppresses the check, because checking feels like confirming something already known. That is the same shape as reading a function's name for its meaning: an answer supplied before the question was asked.

Sweep what cites a record when you correct it, not only the record. This is the same family as knowing an instrument's frame - it is knowing what a correction actually reaches - and it is the one discipline here that currently has no owner. Superseding a decision record is somebody's job; sweeping the always-on rules that cite it is nobody's. The two are one surface with two read paths, and the quieter path is the one that gets fixed. A superseded record is inert until something cites it, whereas a rule citing it enters every agent's context on every dispatch, which makes the rule the LOUDER path and the one that keeps a retired conclusion operative.

The worked instance cost this campaign twice in one day through two separate doors. A live-measured HTTP 404, correct about the host it was measured against and wrong about the endpoint, was recorded as "AEAT exposes no read-only censal projection". The first door was the record itself, which made a reader look unbuildable and produced a refusal to build it. That was corrected by marking the record superseded and stating in its body which claim was disproven. The second door stayed open: an always-on rule still told every agent the censo pull was retired and censal facts were operator-manual, citing the superseded record. Any agent handed the work to restore that verb would have read the rule, refused, and been correct to. Correcting the record did not reach the rule, because nothing connects them in the direction a correction travels.

So a correction is not complete when the record is right. It is complete when nothing still in force asserts the retired conclusion. In practice: search the rule corpus, the harness documents and the skills for the corrected record's stem and for its conclusion in prose, since a citation by claim is as binding as a citation by name and harder to find. The claim survives its citation, and prose has no backlinks.

Prefer ownership transfer over window narrowing for shared-subject work. The staged-patch drive is correct and should remain the technique for landing into a file another agent holds, but this session showed its verification step is a detector rather than a guarantee. Where the file has an active owner who is about to edit the same region, handing them the change removes the race instead of scheduling around it, and that is a resolution rather than a workaround. Where no owner is available, the apply, the verification and the commit should be one uninterruptible operation.

Re-verify state at the moment of acting. This applies to agents reading a peer's report and to whoever is coordinating them. A report is a description of a past state, and in this worktree the interval between a report and a decision made on it is routinely long enough for the decision to be wrong. The cheap discipline is a state check immediately before acting, not immediately before deciding. A worked instance: a step was reported closeable from a reading taken against the working tree rather than the committed content, the instruction to close it was issued on that report without an independent check, and the claim became true only because a third agent committed in the interval. Pinning a closure measurement to a single commit and quoting that commit is the repair, and it is cheap enough to apply to every step closure rather than only to contested ones.

Report observed escapes; probe inferred gaps before reporting them. This is the discipline the withdrawn instance above cost, and it applies to every finding in this record. An escape that HAPPENED carries its own evidence: the value was written, the artefact exists, and the claim is about the past. A gap inferred from structure - this catalogue lacks that section, this field is typed as a string, therefore nothing is enforced - is a hypothesis about the future dressed as an observation, and names are its main input. A function named like a validator and a field named like a hole will support a confident, specific, entirely wrong finding. Both kinds are worth reporting, but an inferred gap must be stated as an inference until a probe against the real path settles it, and such a probe is usually cheap: five lines against the real store disproved the claim here, and would have done so before it reached a decision record. The failure mode is not carelessness, it is that structural inference produces findings that look BETTER than observations, because they generalise.

Place every gating check where a failure halts. This is the fourth class's whole remedy and it is positional, not analytical: no amount of making the check more correct helps, because the check was already correct. Where the project's guidance recommends confirming something before acting, it should show the two in one construct that aborts, not as adjacent steps with a human or an agent expected to read between them. A printed confirmation is not a gate, and the distinction is invisible in a passing run - the output looks identical whether or not anything is reading it.
