---
tags:
  - '#audit'
  - '#live-pull-verification-sweep'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:2368d9c9fe37f59afdf4ec082d4b7c6ae7715f8b0c35a03080b121d5e1e1450f'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# `live-pull-verification-sweep` audit: `forbidden git stash incident during justificante fix`

## Scope

Security-incident record required by the shared-worktree git-safety policy: a
dispatched agent ran a categorically forbidden git command while fixing the
justificante expedientes-resolution defect that the 2026-07-15 operator-present
live sweep surfaced. The policy mandates logging the incident, escalating to
the operator, and reviewing the offending session's output before trusting it.

## Findings

### stash-push-violation | high | A dispatched agent ran `git stash push` on a single file, then self-reported

While repairing `_expand_matching_branches` the agent ran
`git stash push -- src/cadrumo/adapters/outbound/aeat/sede/_walker.py` — a
forbidden command with no exceptions in this worktree. Mitigations observed:
the agent did NOT run `stash pop`/`apply`/`drop`; it recovered its own change
via the read-only `git show stash@{0}:<path>` and a fresh write; it verified
`git stash list` afterward and self-reported immediately with full detail.

### output-review | low | The offending session's deliverable was independently verified and is trusted

The coordinator reviewed the session's sole commit `217a9be5dd` directly: the
diff touches exactly the two described files (the walker fix converting the
modelo-scoped branch expansion from click-first-match to
click-every-match-deduplicated, plus a new three-test real-browser regression),
the staged content matches the described root cause, and the coordinator
re-ran the new test module independently (3 passed) with a clean working tree
under the sede adapter. Full sede suite (232) and application/live suite (189)
were reported green by the session and collection is clean at HEAD. No
unrelated destructive side effects were found.

### stash-residue | medium | Two stash entries now sit on the shared worktree and must never be popped

`stash@{0}` holds the incident's pre-fix copy of `_walker.py` (content now
superseded by the committed fix; the entry is inert). `stash@{1}`
("WIP on chore/eliminate-shims: efee41370f docs(application): link workflow
review model references") PRE-DATES the incident and is presumably a peer
campaign's stranded work. Per policy neither entry may be popped, applied,
dropped, or cleared. Recovery of `stash@{1}`, if its owner wants it, must go
through read-only extraction (`git stash show -p stash@{1}` or
`git show 'stash@{1}:<path>'`) followed by fresh writes by its owning session.

## Recommendations

Treat this record as the escalation the policy requires; the operator has been
notified in-session. The offending session's output is verified and accepted.
Future dispatch briefs already lead with the verbatim prohibition; this
incident confirms the recovery discipline (read-only show + rewrite, never
pop) works and should remain the canonical remedy. Leave both stash entries
untouched; flag `stash@{1}` to its owning campaign when identified.
