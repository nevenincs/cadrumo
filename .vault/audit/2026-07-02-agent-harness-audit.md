---
tags:
  - "#audit"
  - "#agent-harness"
date: '2026-07-02'
promoted_to:
  - 'rule:subagent-commits-require-explicit-pathspec'
modified: '2026-07-02'
---
# `agent-harness` audit: `git index sweep incident 84f84166f`

## Scope

Records a shared-worktree git-safety incident that occurred while orchestrating
the DAE-80 agent-harness rollout with Sonnet-5 execution subagents on the
`chore/eliminate-shims` branch on 2026-07-02. Logged per the git-worktree-safety
discipline, which requires incidents to be recorded in the audit trail and
escalated to the operator.

## Findings

### no-pathspec-commit-swept-peer-staged-work | high | a subagent's `git commit` with no pathspec bundled 35 peer-staged files into commit 84f84166f

A Sonnet-5 execution subagent tasked with a one-line change (retiring the
`LIVE_READ` mutability enum member) verified its own target file carried no peer
WIP, then committed with `git add -- <its file>` followed by a `git commit`
carrying NO pathspec. The shared index already held a peer campaign's staged
work - 35 files of an unrelated `cross-domain-continuity` effort (renta
cuota-chain simplification, anualidades-eligibility removal, several test
rewrites, a completed exec record, and an audit doc). The no-pathspec commit
swept all of it into commit `84f84166f` under the subagent's one-line commit
message. This is exactly the failure mode the `uncommitted-wip-is-not-orphaned`
rule warns against: a no-pathspec commit while a peer has files staged sweeps
their work under a foreign SHA.

Impact assessment: NO data was lost - every swept file is committed and
inspectable via `git show 84f84166f`, and the swept content is complete and
coherent, not half-applied. The single real consequence is attribution: the
peer campaign's own session, when it next commits, will find its staged work
already committed under a foreign SHA and message. The technical change the
subagent intended (the enum retirement) is correct and included in the same
commit; the operator_surface tests pass.

### remediation-was-non-destructive-by-design | low | the sweep was not un-bundled, deliberately

The commit was NOT un-bundled. `git reset`, `git revert`, and `git rebase` are
forbidden in this shared worktree (they would destroy the now-safely-committed
peer work or rewrite shared history), so no surgery was attempted. The
coordinator switched the remaining execution subagents to a strict
no-agent-commit policy (agents leave work in the working tree and report; the
coordinator commits centrally via a HEAD-anchored apply-cached gated drive only
when the index is verified clean of foreign work) and messaged the two in-flight
agents to halt any commit. The commit has NOT been pushed; `git log origin..HEAD`
must be checked before any push so the peer's bundled work is not carried to
origin under this SHA without coordination.

## Recommendations

- Leave `84f84166f` intact (data is safe); do not attempt destructive
  un-bundling. Flag the SHA to the `cross-domain-continuity` campaign so its
  session knows its staged work is already committed and does not re-commit or
  assume loss.
- Enforce the no-agent-commit policy for the remainder of the harness rollout:
  dispatched subagents implement + verify + report only; the coordinator performs
  all commits, one path-scoped or apply-cached commit at a time, after verifying
  the staged set carries zero foreign markers immediately before committing.
- Do not push until `git log origin..HEAD` is inspected and the peer campaign has
  been coordinated with regarding the bundled commit.
- Candidate codification: a dispatch-brief rule that a subagent must NEVER run
  `git commit` without an explicit pathspec, and must verify the staged set is
  exactly its own authored files before any commit - promotable once the pattern
  is confirmed across the rollout.

## Correction (post honesty-review, 2026-07-02)

### impact-assessment-was-wrong-data-was-lost | critical | the "NO data was lost" conclusion above is FALSE, verified against committed HEAD

A fresh-context honesty review verified commit `84f84166f` against committed HEAD
(not the dirty working tree) and found the earlier "swept content looks
complete/coherent, not half-finished ... NO data was lost" assessment is wrong.
The commit permanently removed, from history, the M100 anualidades separate-escala
derivation: `_inject_derived_anualidades_eligibility_facts` in
`application/modelo/_profile_binding.py` (added moments earlier by peer commit
`63f9b6125`) and its 80-line unit test
`application/modelo/tests/test_anualidades_eligibility_derivation.py`, and stripped
`art-64`/`art-75` from the 2024/2025 M100 `renta-cuota-chain` construct
`legal_refs`. But `_data/registry/aeat/user_profile/schema.toml` and the M100
2020-2025 registry bindings STILL reference the deleted `anualidades_sin_minimo_
descendientes_{year}` profile-fact key, so at committed HEAD the M100 anualidades
regime is a broken derivation chain referencing a function that no longer exists -
a silent-under-declaration-class defect (LIRPF art. 64/75), collateral damage from
this campaign's own no-pathspec commit into an unrelated peer feature. The function
and test currently exist ONLY in the dirty working tree (an uncommitted fix in
flight), not in history. Remediation is owned by the peer `cross-domain-continuity`
campaign (regulated tax logic); it must land its working-tree fix, restore
`art-64`/`art-75`, and re-author (verify, not merely restore) the deleted test
before this is closed. The coordinator must NOT unilaterally re-author regulated
tax logic. This correction supersedes the "NO data was lost" line above.
