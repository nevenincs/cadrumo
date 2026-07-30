---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S16'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Run the fresh-context honesty review against the campaign closure summary and persist it as a vault audit with every surfaced item tracked as a new Step or formally deferred with a named follow-up, gate: the audit document exists under .vault/audit and uv run --no-sync vaultspec-core vault plan status reports no checked Step without an exec record

## Scope

- `.vault/audit/`

## Description

- Re-run every suite this campaign touched at the head current to the review.
- Attribute each failure before treating it as owned or disowned.
- Fix the one defect the review found in this campaign work.
- Persist the review as a vault audit document.

## Outcome

The review found a real defect this campaign caused and had not noticed. The
version reset moved every declaration to the zero version but did not re-run the
dependency lock, so the lockfile still pinned the abandoned number for the root
distribution and both companions. That is the exact number the campaign exists
to make unmintable, sitting in the file that decides what a build resolves.

Fixed under the commit subject `fix(release): re-lock after the version reset,
which left the lockfile at the old number`, and the dependency-surface gate now
passes.

The shape of the miss is the reusable part: the change was verified against the
suite nearest its intent, the release suite, rather than the suite nearest the
files it touched. A version change is a packaging change regardless of which
record motivated it.

Full re-run at review time: six hundred and ninety-six tests pass across the
release, packaging, continuous-integration, quality, and deploy suites, with the
two failures both attributed and one fixed.

Five further findings are recorded in the audit rather than actioned here: three
verification readings during the campaign that reported green without running,
a long suite that measured a head three commits stale, the documentation lane
failing for reasons outside this campaign, the deliberately broken pairing of
the guard removal, and the marketplace mechanism never having run against its
real target.

## Notes

The review was worth running on its own evidence. Every Step had passed its own
gate and carried a mutation proof, and the campaign still shipped a lockfile
pinning the version it had just abandoned. A closure review that only re-reads
the records would not have found it; re-running the suites at current head did.
