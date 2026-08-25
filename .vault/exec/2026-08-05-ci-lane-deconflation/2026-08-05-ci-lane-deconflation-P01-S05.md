---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:150eed2a220ef309325c128d6793694933bb9ae39066d764a753569342943690'
step_id: 'S05'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Decide what to do about the already-pushed branch, a peer snapshot pushed it so the original decision is moot and the live question is whether the published history needs remediation

## Scope

- `origin/main`

## Description

- Re-read the Step premise against current published history rather than as written.
- Scan the campaign's own published range for secret patterns (API keys, private key headers, tokens).
- Re-check every escaping form of the operator home-directory token against the current tree.
- Establish whether the one live published-history item this scan surfaced originates inside or outside this Step's scope.
- Determine whether any remedy for it is reachable under the safety rules.

## Outcome

The Step is closed as a no-op: nothing this campaign published requires action.

The premise decayed further than the row records. The row treats the push as a one-off
branch event; publishing to the trunk has since become routine fleet activity, advancing
through five or more further pushes. The aggregate snapshot commit the row refers to
bundles several unrelated campaigns' vault documents and documentation internals into one
commit, which is untidy history but not a defect — no secret pattern appears anywhere in
the campaign's published range.

One genuine published-history problem exists, and the finding that matters is that it is
**not this Step's**. The operator's home-directory token entered published history roughly
six hours before this campaign's push, in a commit reaching back to an underlying date in
April, and was already found and dispositioned by the privacy scrub commit — an ancestor
of this campaign's own push. That commit scrubbed every tracked and untracked working-tree
record, turned the privacy gate green, and states in its own message that it does not
remove the token from published history, and that rewriting a published branch is the
operator's decision.

The two candidate readings were tested rather than assumed, because only one is true.
"Already remediated" holds only at the working-tree level: current records are scrubbed and
the gate is green. "Nothing needed" is false: the published-history question is real. It
simply predates this Step and is independent of what this Step is scoped to.

For the sub-question of remediating published history, no remedy is reachable regardless of
ownership. Rewriting published history is categorically forbidden in this worktree, so the
boundary is itself the answer.

A tracking gap was recorded separately and is not resolved by this Step: the operator
decision currently exists only in a commit message, with no durable record in the decision,
audit, plan, or research corpora.

## Verification

Publication status of the originating commit, and the token's presence there versus at HEAD:

    git merge-base --is-ancestor e0cc5219a8 origin/main
    YES - e0cc5219a8 IS in published history

    git grep -F -l -- 'C:\Users\hello' e0cc5219a8   -> 1 file
    git grep -F -c -- 'C:\Users\hello' HEAD         -> 0 files
    git grep -F -c -- 'C:/Users/<operator>' HEAD         -> 0 files

Both path-escaping forms are absent from the current tree while the backslash form is
present in the published commit, which is the exact split the scrub commit's message
claims. Patterns were compared with `-F` on both sides so a metacharacter could not match
a filename in place of the token.

## Notes

The investigating agent's findings were re-measured before this record was written rather
than transcribed. Two claims were load-bearing and both were confirmed independently: the
scrub commit's message says what was reported verbatim, and the originating commit is
genuinely an ancestor of the published trunk.

The bare surname token appears in 35 files at HEAD and is not evidence of a leak — it is an
ordinary English word. Only the full path forms identify the operator, which is why both
were tested separately.

An open item leaves this Step unresolved but out of scope: the published-history decision
belongs to the operator and is tracked only in a commit message. Whether to give it a
first-class record is a decision for the operator, not for this campaign to take
unprompted.
