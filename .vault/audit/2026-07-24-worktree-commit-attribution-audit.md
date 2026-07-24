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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace worktree-commit-attribution with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

### attribution-is-the-loss-not-data | medium | Nothing is destroyed, which is why it goes unnoticed

No capture lost work, stranded a peer, or reddened a gate. Every affected change is present and correct at HEAD, which is why none of the three was caught by any test, review, or checklist.

What breaks is the ability to answer "who changed this line, and why" from `git log --follow` — the first tool a later reviewer reaches for, and the one a swept commit silently misinforms. The compounding factor is that every commit in this worktree carries the same git author identity, so authorship cannot discriminate between agents either. The result is a history with neither authorship attribution nor index isolation, in which a commit message describes a subset of what the commit contains.

### exec-record-frontmatter-date-is-evidence | medium | Aligning a retroactive record's date to its siblings falsifies it

Nine retroactive execution records were scaffolded with an explicit `--date` matching their sibling records rather than the real authoring date, placing their frontmatter a week before the day they were written. Each record's prose disclosed the retroactive authoring honestly; the frontmatter contradicted the prose.

The reviewer this misleads is the one behaving correctly. Scanning frontmatter dates is the normal way to assess vault staleness and to confirm when a plan's completeness claim became true, and a reader doing that would have concluded several campaigns were complete days earlier than they were. A separate incident of the same shape was corrected independently in the same session, which makes it a pattern in how retroactive records get authored rather than one author's slip.

The scaffolding verb's `--date` override is legitimate for reconstructing a genuinely older record. Using it for visual tidiness against sibling rows is not.

### bare-pytest-path-is-not-a-verification | medium | The default marker expression silently selects nothing

The default pytest configuration pins a marker expression selecting only the unit lane. Invoking `pytest <path>` against an integration-marked module therefore matches nothing and exits successfully, reporting "no tests ran" rather than any failure.

This produced a would-be false green three separate times in one session while agents verified other agents' gates. It was caught every time by the harness's own deselection banner, which states that a green result there means the selection matched nothing rather than that the code is sound. That banner is load-bearing and should not be removed or quieted.

## Recommendations

Treat `git diff -- <file>` before the first edit as the branch point rather than a formality. If it shows content that is not yours, the file is entangled and the tool must change; if it is clean, a pathspec commit is correct and sufficient.

For an entangled file, use the apply-cached gated drive documented in `uncommitted-wip-is-not-orphaned`: write the committed version aside with `git show HEAD:<path>`, apply only your own edits to that copy, diff it into a HEAD-anchored own-edits-only patch, stage it with `git apply --cached` so the peer's live working-tree state is untouched, verify the staged diff carries zero foreign markers, then commit the verified index.

The drive's final step is a **bare commit with no pathspec**, and this is the part that has repeatedly gone wrong. A pathspec naming an apply-cached path discards the carefully-verified index and re-reads the working tree, which is the sweep the drive exists to prevent — so the drive is silently defeated at its last step by the command that feels like the safe one. There is no case in which a pathspec over an apply-cached path is correct. Four prior incidents of exactly this shape are on record from earlier sessions, one of them with the index already staged perfectly, which is what makes it worth stating as an absolute rather than a caution.

A bare commit is only safe when the index holds nothing but your own staged work, and in this worktree that condition frequently does not hold — the shared index routinely carries dozens of peer-staged files. When a file is genuinely entangled AND the index carries peer-staged paths, no git primitive is clean: a pathspec sweeps the peer's working-tree lines, and a bare commit sweeps the peer's staged files. In that situation the correct move is to **serialize** — commit unrelated clean files by pathspec first, then let each owner land its own entangled file in turn — rather than pick the less-bad command.

Do not treat a short edit-to-commit window as the remedy. It reduces exposure and does not remove it; one capture in this session occurred inside a window of a few minutes.

Scaffold every execution record with its true authoring date, and let a retroactive record's date differ from its siblings. Where the date is genuinely reconstructed, say so in the record's own prose, which several of these records already did correctly.

Verify a gate in the lane that actually owns it. A run reporting no collected tests is an unverified gate, not a passing one.

The identity-collapse half of the attribution problem — one git author across every agent — cannot be addressed from inside an agent session and needs an owner at coordinator level.
