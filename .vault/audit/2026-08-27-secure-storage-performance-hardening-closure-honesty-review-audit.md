---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:4ff916ae8401fd0a01dd70f391bcb86ec3d7e14936d465390e3a1a0583e0efb9'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-27-secure-storage-performance-hardening-measured-outcomes-reference]]"
  - "[[2026-08-27-secure-storage-performance-hardening-w02-demand-loading-residue-audit]]"
---

# `secure-storage-performance-hardening` audit: closure honesty review

Read as if inheriting this campaign cold: what does the plan CLAIM, and what is
actually true of the tree?

## The finding that shaped everything else

Six W02 Steps were marked complete while their outcomes did not hold. The
`W03.P08.S32` cold-process contract was the first gate to run a whole command
end to end, and on its FIRST run it failed on three properties W02 had already
claimed. Chasing those surfaced three more.

That is the failure the orchestration rule names: delivered-as-specified and
recorded-but-not-implemented wearing the same checkbox. It is the reason every
closure below states its exclusion, and the reason S47's criteria were
re-verified here rather than inherited from W02.P03a's marks.

## Verified directly, not inherited

| S47 criterion | Result |
| --- | --- |
| Forbidden command-JSON names absent from tracked tree | **absent** |
| Development generators absent from `src/` | **absent** |
| Every live node classified (capabilities) | **365 of 365** |
| Every live node classified (performance class) | **365 of 365** |
| Every live node classified (side effects) | **365 of 365** |

## What each closure EXCLUDES

A campaign may not narrow its own completion criterion silently. Each Step
closed here is narrower than its wording, and this is the list.

- **S33** (declared families) -- 23 of 25 capability groups clean. EXCLUDES two
  groups, `encrypted-facts` and `encrypted-facts,network`, both named with
  their cause and carrying stale-entry cases.
- **S35** (defer until execution) -- 351 of 365 nodes defer everything.
  EXCLUDES 14 named nodes that still pay registry or persistence cost at
  resolution, so an operator reaching a sibling or running `--help` near them
  still pays it.
- **S36** (import-graph checks) -- both halves exist and run; the static half
  was restored from a total abort. EXCLUDES the fact that it reports **6 broken
  contracts**, including the layered architecture contract itself. "The checks
  run" is not "the layering holds".
- **S39** (side effects) -- 93 exercisable leaves green. EXCLUDES three
  commands that create the encrypted database through the cold-bootstrap store,
  carried as a reasoned allowlist with stale detection, and the derived `cache`
  tree and `.lock` files, excused by a documented predicate.
- **S37** (budgets) -- REWORKED, not delivered as written. Latency budgets are
  not measurable on this infrastructure: a quiet-control resolution takes ~1.75s
  and peers routinely run 200 concurrent processes, so wall-clock readings track
  contention. Replaced by a deterministic per-class module-cost budget. EXCLUDES
  any claim about wall-clock latency.

## What this campaign did NOT do

- **S43 (full-suite green) is not achievable by this campaign alone.** The tree
  is red from concurrent peer work: 158 failures in `application/modelo`
  (proven pre-existing by a baseline worktree at the commit before this
  campaign's facade change -- identical 163-name failure sets), 19 in the CLI
  suite, 7 in storage, all attributed to peers' registry-evidence, verb-rename
  and relocation work. Marking S43 complete would assert a green tree that does
  not exist.
- **The 6 broken import-linter contracts are not fixed.** They belong to the
  TUI and llm campaigns. Restoring the enforcement that reveals them is this
  campaign's contribution.
- **The `CommandSideEffectClass` taxonomy gap is not closed.** There is no
  member meaning "writes a derived cache", so nine leaves sit in a gap that a
  documented predicate excuses rather than a declaration describes.

## Judgement

The campaign's own goal -- make command loading proportional to the selected
path, and make profile listing a pure read -- is met and gated. The residues
are enumerated, each carries a stale-entry case that fails the moment it stops
applying, and none is silent.

The honest reading of this plan at closure is: **the properties it set out to
establish are established and defended by gates; the tree around them is not
clean, and the campaign says so rather than implying otherwise.**
