---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:9d891022b8b56d7b7a10d6a5455516d41ae7f7cfcacffb4855a93f5c15989f8a'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` audit: `the reserialisation finding is disproved and its cause misattributed`

## What was claimed

That `vaultspec-core vault plan step check` reserialises a plan and strips template comment
blocks — 93 lines on this campaign's plan — while its `--dry-run` previews only the checkbox
line, so an operator who previews and then commits on the strength of that preview commits a
diff they have not seen.

I reported that. Two people subsequently observed the same 93-line strip and reached the same
attribution independently, which made it look corroborated. It is wrong.

## What the reproduction found

Built an isolated vault outside the repository, copied in this campaign's plan **as first
committed** (222 lines, 7 comment blocks including the LINK RULES and FRONTMATTER RULES
blocks), and ran the verb against that exact artefact.

`step check` on the real plan changed **one line**:

    -body_hash: 'sha256:72ef15e6c22de8896928efbe4845bd81f9d30bda272cf0bca153f70e0d771e4c'
    +body_hash: 'sha256:894e430331665457a566ea7f0e5d07710a3fb9fed73d95e91e888e53135cbd8b'

File length before and after: 222 lines, unchanged. Comment blocks: 7, unchanged. The
`--dry-run` preview for the same operation showed that line **plus** one prose-reflow line
that the real run did not produce — so the preview **over-showed** rather than hiding
anything. On a freshly scaffolded plan the same asymmetry appeared in the same direction
(preview 6 additions against an actual 4).

**The claim is disproved in the direction opposite to how it was filed.** `step check`'s
preview is faithful, and if anything it is pessimistic.

## What actually stripped the file

`vaultspec-core vault check all --fix`, run against the same isolated copy:

    222 lines -> 129 lines
    7 comment blocks -> 0
    exactly 93 lines removed

93 is the number observed on the campaign plan, matched exactly rather than approximately.

**And that behaviour is documented, so it is not a defect at all.** The vault rulebook states
that `vault check all --fix` "reconciles frontmatter, **strips leftover template
annotations**, and applies markdown hygiene fixes". It did precisely what it advertises.

## Why the misattribution happened, which is the durable part

I ran `step check`, then ran `git diff` on the plan, and read the resulting diff as the effect
of my own last command. It was not. A peer's tree-wide `--fix` run had already stripped the
file, and the diff I was reading was accumulated working-tree state against HEAD.

**In a shared worktree, `git diff` after your own mutation attributes every peer change since
HEAD to you.** The diff is a statement about the tree, never about your delta. Isolating a
delta requires a snapshot taken immediately before the command — which is exactly what the
reproduction did and what the original observation did not.

That this reproduces the whole session's recurring shape is worth stating plainly: the
instrument answered a neighbouring question. `git diff` answers "how does the tree differ from
HEAD", and I asked it "what did my command do".

Two people agreeing did not help, and is the second instance today of that specific trap.
Both of us ran the same wrong instrument against the same contaminated tree, so the agreement
measured the shared method rather than the fact — corroboration, not confirmation.

## Disposition

**No upstream report is warranted and none should be filed.** The verb behaves correctly, its
preview is faithful, and the strip belongs to a different verb whose documentation describes
it.

The genuine hazard here is one already known and already recorded: `vault check all --fix` is
**tree-wide**, so running it in a shared worktree rewrites peer-owned documents — stripping 93
lines from a plan whose author did not invoke it, and touching every other document's stamps
in the same pass. That is a scope property of a documented verb, not a bug in it, and the
existing operating guidance to scope checks to one's own documents already covers it.

## What would have caught this earlier

A before-snapshot. One `cp` immediately before the mutation converts "the tree differs" into
"my command did this", and it is the only thing that distinguishes them in a worktree that
moves at roughly nineteen commits per twelve minutes.

The retraction cost less than the investigation, which is the argument for testing a harness
finding before filing it rather than after.
