---
tags:
  - '#audit'
  - '#worktree-commit-attribution'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - "[[2026-07-24-ledger-evidence-atomicity-close-honesty-review-audit]]"
  - "[[2026-07-24-auth-cert-recovery-custody-close-honesty-review-audit]]"
---

# `worktree-commit-attribution` audit: `Working-tree capture, pathspec isolation, and record-date honesty`

## Scope

Two process defects observed repeatedly across a single multi-agent session on 2026-07-24, both of which corrupt the evidence a later reviewer relies on while destroying nothing and failing no gate. Neither is a code defect, so neither would surface in any test lane.

The first is working-tree capture: one agent's uncommitted edits landing under another agent's commit. Three independent instances, different agents, opposite directions. The second is record-date backdating: retroactive execution records carrying a frontmatter date earlier than their real authoring date.

This record exists because both are invisible to the quality gates and both mislead specifically the reader who is doing the right thing — checking history, or scanning dates for staleness. Codification is retired in this project, so this is an audit record rather than a rule.

## Findings

### pathspec-commit-takes-the-working-tree | high | A pathspec commit feels like isolation and is not

`git commit -- <pathspec>` commits the WORKING-TREE content of those paths. If a peer has uncommitted edits in the same file, a pathspec commit takes those edits too. It scopes which files are committed; it does not scope whose changes within them.

This is the mechanism behind every capture below, and it is dangerous precisely because it feels safe. Each agent believed it was committing narrowly, and the belief was half right: the file set was correctly narrow, the content was not. The staging step is a separate matter — `git add -- <paths>` does scope the index, but a subsequent pathspec commit ignores the index for those paths and re-reads the working tree.

The distinction that matters in practice: for a file carrying no peer edits, a pathspec commit is correct and remains the default. For an entangled file it is the wrong tool, and committing faster does not help — the window is not the problem, the read source is.

### three-independent-captures-in-one-session | high | Different agents, opposite directions, same mechanism

Instance one is recorded as the low-severity `pathspec-commit-swept-peer-locale-wip` finding in the ledger-evidence-atomicity close review: an agent's pathspec commit swept a peer's uncommitted locale work.

Instance two ran the other way. Five plan `related:` edits made through `vaultspec-core vault link add` sat unstaged in the working tree between the verb run and a feature-index regeneration, and a peer's broad commit `9a8de9d40a` carried all five. The sixth edit of the same batch, deliberately held back while another agent finished in that file, was committed by its own author as `f149f63349`. The content is correct at HEAD in both cases; only the attribution differs, and it differs for reasons unrelated to the work.

Instance three ran the first direction again and hit the agent who had raised instance one: four locale-catalogue keys were captured by `6a75aa540f` and `2c185ba9b4`.

Three instances, three agents, one session. That rules out individual carelessness as the explanation.

### nine-day-old-precedent-recovered-by-a-forbidden-command | high | The hazard has previously driven an agent into destructive git

The three captures on 2026-07-24 are not the first. A commit dated 2026-07-15 on the shims-elimination branch is titled "un-sweep peer WIP accidentally committed", naming four step ids, and a stash entry sits on top of it, recorded by git as taken while HEAD was at that commit.

Two things follow. The hazard is nine days older than the session that surfaced it, and nobody carried the lesson forward — which is the argument for this record existing at all rather than the observation living in one agent's transcript. And the recovery reached for `git stash`, which is categorically forbidden in this worktree precisely because it captures every concurrent campaign's work into one blob and strands peers on a partial pop. An agent recovering from a sweep therefore performed a second, more dangerous operation than the one that caused it.

The residue is still present: two stash entries, nine days old, on a branch other than the working branch, holding content nobody has claimed. They must not be dropped — dropping is itself forbidden, and they may hold real work — so the recovery has left a permanent artefact that no one can safely resolve. That cost belongs in any assessment of the hazard's severity: it is not only attribution damage, it has already produced an unresolvable residue and a rule violation.

### attribution-is-the-loss-not-data | medium | Nothing is destroyed, which is why it goes unnoticed

No capture lost work, stranded a peer, or reddened a gate. Every affected change is present and correct at HEAD, which is why none of the three was caught by any test, review, or checklist.

What breaks is the ability to answer "who changed this line, and why" from `git log --follow` — the first tool a later reviewer reaches for, and the one a swept commit silently misinforms. The compounding factor is that every commit in this worktree carries the same git author identity, so authorship cannot discriminate between agents either. The result is a history with neither authorship attribution nor index isolation, in which a commit message describes a subset of what the commit contains.

### exec-record-frontmatter-date-is-evidence | medium | Aligning a retroactive record's date to its siblings falsifies it

Nine retroactive execution records were scaffolded with an explicit `--date` matching their sibling records rather than the real authoring date, placing their frontmatter a week before the day they were written. Each record's prose disclosed the retroactive authoring honestly; the frontmatter contradicted the prose.

The reviewer this misleads is the one behaving correctly. Scanning frontmatter dates is the normal way to assess vault staleness and to confirm when a plan's completeness claim became true, and a reader doing that would have concluded several campaigns were complete days earlier than they were. A separate incident of the same shape was corrected independently in the same session, which makes it a pattern in how retroactive records get authored rather than one author's slip.

The scaffolding verb's `--date` override is legitimate for reconstructing a genuinely older record. Using it for visual tidiness against sibling rows is not.

### apply-cached-applied-index-first-breaks-the-tree | high | The mitigation for capture can itself cause a fleet-wide outage

`git apply --cached` stages hunks **without touching the working tree**, which is exactly the property that preserves a peer's live edits. It is also a trap: after that step the index carries the change and the working tree does not, and the working tree is what every other agent imports, runs, and reads.

An agent used the drive correctly to avoid committing a peer's uncommitted facade-module work, and the peer's work was preserved perfectly. But the change was two-sided — a facade export plus its consumer — and the index was staged before the same lines were mirrored into the working tree. The tree therefore spent a window with the consumer switched over and the export missing, in a module reached transitively by every command surface. Three agents reported the repository broken, and at least two re-attributed their own unrelated failures to it. A formatter then re-sorted the staged import and widened the window.

The correction is one line of sequencing that the drive's description does not state: **apply to the working tree first, stage to the index second.** The rule documents the index mechanics without saying when the tree edit belongs, and index-first is the natural reading of a procedure whose headline step is `--cached`. Applied in the wrong order, the remedy for an attribution problem manufactures an availability problem, which is strictly worse than the defect it prevents.

### own-only-patch-is-reconstructed-not-extracted | high | A marker grep cannot establish that a patch is own-only, and the formatter is not scoped to your hunks

The apply-cached drive depends on building a patch containing only your own edits. That patch is **reconstructed by hand** from a HEAD copy, not extracted by any tool, so its correctness rests entirely on the author correctly identifying which working-tree lines are theirs. Two things defeat the obvious way of checking that.

A marker grep is not sufficient. An agent building an own-only patch for a ledger actions module searched the diff for the peer's principal symbol, got no hits, and nearly concluded the diff was clean. Reading the complete diff instead showed two unrelated peer lines — an em-dash correction and a flag rename from a `--from-csv` spelling to `--file` — that no symbol search would have surfaced. Peer edits do not reliably contain a greppable marker; incidental fixes are exactly the shape that has none.

The formatter compounds this, and this is the part that is easy to miss: a formatter rewrites the **whole file**, not your hunks. On a contended file it can move or reformat lines a peer authored, and those reformatted peer lines then sit in the working tree indistinguishable from the author's own state. A reconstruction that trusts "what changed since HEAD is mine" therefore absorbs formatter-driven changes to lines the author never wrote, and the own-only patch quietly stops being own-only.

Evidence strength, stated honestly because it differs between the two halves: the desync half is confirmed by incident — a formatter re-sorted a staged import and widened the tree-inconsistency window described above. The peer-line-absorption half is reasoned from the mechanism rather than observed; in that incident the formatter re-sorted only the author's own import and left the peer's already-sorted line untouched. It is recorded as a hazard with one confirmed half, not as two incidents.

### the-two-techniques-are-not-interchangeable | medium | Each protects one side and exposes the other

The two available commit techniques fail in opposite directions, which is why neither can be a default for every case.

The apply-cached drive protects the peer's content and risks an inconsistent working tree: it stages without touching the tree, so a half-applied two-sided change leaves the tree broken for everyone until the author mirrors it. A pathspec commit keeps the tree consistent — it commits exactly what is on disk — and risks swallowing peer lines, because what is on disk includes the peer's uncommitted edits.

A same-session instance of the pathspec direction is commit `2781ef0dc6`, whose sweep required two follow-up corrections. The choice between the techniques is therefore conditional on one fact, established by reading the file's working diff before the first edit: peer content present means the drive, peer content absent means a pathspec. Reaching for either reflexively is the error.

### bare-pytest-path-is-not-a-verification | medium | The default marker expression silently selects nothing

The default pytest configuration pins a marker expression selecting only the unit lane. Invoking `pytest <path>` against an integration-marked module therefore matches nothing and exits successfully, reporting "no tests ran" rather than any failure.

This produced a would-be false green three separate times in one session while agents verified other agents' gates. It was caught every time by the harness's own deselection banner, which states that a green result there means the selection matched nothing rather than that the code is sound. That banner is load-bearing and should not be removed or quieted.

## Recommendations

Treat `git diff -- <file>` before the first edit as the branch point rather than a formality, and read it whole. If it shows content that is not yours, the file is entangled and the tool must change; if it is clean, a pathspec commit is correct and sufficient.

The two techniques are not interchangeable and neither is a safe default. The drive protects the peer's content and exposes the working tree; a pathspec commit protects the working tree and exposes the peer's content. One fact decides between them — whether the file currently carries peer edits — and that fact is only available from a full read of its diff.

For an entangled file, use the apply-cached gated drive documented in `uncommitted-wip-is-not-orphaned`: write the committed version aside with `git show HEAD:<path>`, apply only your own edits to that copy, diff it into a HEAD-anchored own-edits-only patch, stage it with `git apply --cached` so the peer's live working-tree state is untouched, verify the staged diff, then commit the verified index.

Read the **complete** working-tree diff before reconstructing that patch, and read the complete staged diff before committing it. Do not substitute a grep for the peer's symbol or for any other marker: peer edits frequently carry no greppable marker at all — an incidental typo correction or a flag rename has none — and a formatter rewrites the whole file rather than your hunks, so peer lines it has moved or reformatted will sit in your tree looking exactly like your own work. Any line you did not author is a peer line and belongs reverted in the scratch copy before the patch is built. The own-only patch is reconstructed by hand, not extracted by a tool, so nothing but a full read establishes that it is own-only.

The drive's final step is a **bare commit with no pathspec**, and this is the part that has repeatedly gone wrong. A pathspec naming an apply-cached path discards the carefully-verified index and re-reads the working tree, which is the sweep the drive exists to prevent — so the drive is silently defeated at its last step by the command that feels like the safe one. There is no case in which a pathspec over an apply-cached path is correct. Four prior incidents of exactly this shape are on record from earlier sessions, one of them with the index already staged perfectly, which is what makes it worth stating as an absolute rather than a caution.

Sequence the drive as working tree first, index second. Apply your edits to the working tree, confirm the tree is self-consistent and importable, and only then stage the HEAD-anchored own-only patch with `git apply --cached`. Staging first leaves the tree carrying half of a two-sided change for as long as the drive takes, and the tree is the surface every other agent is running against.

A bare commit is only safe when the index holds nothing but your own staged work, and in this worktree that condition frequently does not hold — the shared index routinely carries dozens of peer-staged files. When a file is genuinely entangled AND the index carries peer-staged paths, no git primitive is clean: a pathspec sweeps the peer's working-tree lines, and a bare commit sweeps the peer's staged files. In that situation the correct move is to **serialize** — commit unrelated clean files by pathspec first, then let each owner land its own entangled file in turn — rather than pick the less-bad command.

Do not treat a short edit-to-commit window as the remedy. It reduces exposure and does not remove it; one capture in this session occurred inside a window of a few minutes.

Scaffold every execution record with its true authoring date, and let a retroactive record's date differ from its siblings. Where the date is genuinely reconstructed, say so in the record's own prose, which several of these records already did correctly.

Do not reach for `git stash` to recover from a sweep. It is categorically forbidden here, it is more dangerous than the sweep it repairs, and the 2026-07-15 precedent shows it leaves residue nobody can safely resolve afterwards. A sweep loses nothing; the correct response is to record the mis-attribution and move on, not to attempt a repair with a destructive primitive.

Verify a gate in the lane that actually owns it. A run reporting no collected tests is an unverified gate, not a passing one.

The identity-collapse half of the attribution problem — one git author across every agent — cannot be addressed from inside an agent session and needs an owner at coordinator level.
