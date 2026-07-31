---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:9c5dd829dea0f62a4737d95ebbb75e2809e300601dac85dacee44f7b9edda8b3'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
step_id: 'S02'
---

# FORMALLY DEFERRED to the discovery service's own repository, signal a degraded state on the semantic discovery service so a truncated index either refuses to answer or marks its answers untrustworthy, because the governing rule makes an agent refuse coding work when the service is DOWN while a service that ANSWERS from a partial index never trips that refusal, re-measured on 2026-07-28 against this tree's project-local store where the truncated case still carries no signal and status reports code as not indexed yet beside 70054 answering sections

## Scope

- `external, vaultspec-rag repository not this tree`

## Description

- Read the new start-refusal audit in full and establish which site of the defect class it actually covers.
- Re-measure the premise rather than inherit it, since this tree no longer reads the store the row was written against.
- Probe the empty axis directly rather than assume it answers silently.
- Separate what improved from what did not, so the deferral names the residue precisely.
- Record the compensating controls now carrying the risk, and that neither is durable.
- Close as formally deferred with the external follow-up named, and name the in-tree option that is a different row rather than this one.

## Outcome

Closed as formally deferred. The row cannot be implemented from this tree and the audit does not discharge it, so the closure rests on a named external follow-up rather than on the audit.

The audit covers a SIBLING site, not this one. Its subject is the service's startup path, where four sequential witness probes share a two-second budget and the third shells out to a call measured at 2794, 3421 and 3680 milliseconds, so a timeout is rendered as an identity failure. Its three recommendations all bind that path. S02 is about the ANSWERING path, where a partial index returns results with no trustworthiness marker. Same class, stated as such by the audit itself, different site. Reading the audit as covering S02 would be the stretch, and it is declined.

The premise moved and the defect survived the move, which is the new evidence. The row was measured against the machine-global service at 1027 code sections. This tree no longer uses that service: it reads a project-local store built with the fallback path. Measured today, that store reports 70054 source-code sections and simultaneously reports its code generation as `not indexed yet`, so the count and the generation marker contradict each other. Code searches run against it during this session returned real, diverse, relevant results, which settles that the 70054 sections are usable and the generation marker is wrong rather than the reverse. So a consumer reading generations concludes code search is unusable, a consumer reading counts concludes it is fine, and neither reading is a degraded signal.

One thing genuinely improved and is recorded so a later reader does not re-derive it. A search against an axis holding zero documents does not return a bare empty result. It prints a `Why` line stating that no matching documents were found in the local index, and points at the indexing and status verbs. That is a partial signal for the EMPTY case.

It is not a signal for the TRUNCATED case, which is what S02 is about. The `Why` wording does not distinguish an axis that is empty from an axis that is populated and simply did not match, the call still exits zero, and a truncated-but-nonempty axis produces ordinary-looking results carrying nothing at all. So the failure S02 names is unchanged, and it is now reproducible on two independent backends.

The compensating controls are real and neither is durable. The first is prose: every dispatch brief carries a hand-written warning naming the inverted failure condition, which is an instruction an agent may not follow and which decays the moment a brief is written without it. The second is the local store itself, which lives under a gitignored path, so it is untracked, per-worktree, invisible to peers, not reproducible from the repository, and its health cannot be asserted by any committed check.

Follow-up, named: the degraded-state signal belongs in the discovery service's repository, alongside that repository's handling of the audit's startup-path recommendations, since both are the same principle applied at two sites — report inability to tell as its own state rather than as a definite answer.

## Notes

A second, different remedy exists and is deliberately NOT claimed as this row. An in-tree preflight could assert the local store's health before an agent trusts a search, which would convert the prose control into a mechanical one without touching the external product. That is in-tree work, it is a new row rather than this one, and it is left for the coordinator to commission or decline rather than started unasked.

The empty-axis finding is reported as an improvement rather than folded into the negative, because the honest shape of this measurement is mixed and reporting only the part that supports the row would be the same selective reading this campaign exists to catch.

Not verified: whether the generation marker reading `not indexed yet` beside a working store is the same defect as the truncated-index silence or a second independent one. Both are consistent with the evidence and separating them needs the service's own source, which is external.

The service was confirmed stopped throughout, so every measurement here is of the project-local store and none of it describes the machine-global instance. No start, stop, or rebuild was attempted, on the audit's finding that retrying under contention is destructive.
