---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:36214d97da994bffd1f3f699f2b71615000f6b8dec7264412981f78afc106718'
step_id: 'S08'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Measure the dev tooling gates at a clean HEAD, the local count of 55 is contaminated because 32 belong to an uncommitted peer legal entry and the true figure is nearer 23

## Scope

- `dev/audit`
- `dev/deploy`
- `dev/env`
- `dev/registry`
- `dev/docs`

## Description

- Extract committed HEAD into a clean directory rather than waiting for the worktree to settle.
- Run the dev-tooling selection twice and intersect, rather than trusting one pass.
- Classify every failure before counting it.

## Outcome

Measured at extracted HEAD `b90729b04a` — `git archive` into a clean directory, 40,224 files,
containing no dirty file by construction:

    selection   -m "(unit or integration) and not resident_service" over the ten dev/ dirs
    run 1       20 failed, 903 passed, 4 errors
    run 2       20 failed, 903 passed, 4 errors      intersection identical
    guard       HEADGUARD OK on both runs - cadrumo resolves inside the extraction

    classified  6 REAL (conformance baseline)  +  18 unmeasurable by this instrument

**The row's precondition was dissolved rather than satisfied.** It asked for "a clean HEAD",
which had been read as waiting for the worktree to settle — and this worktree does not settle;
it has carried 130-160 uncommitted paths all day. A `git archive` extraction contains no dirty
file by construction, so it answers the question the row was actually asking without requiring
the condition the row assumed. The correction came from `entrypoints-fixes`.

## Verification

    git cat-file -t b90729b04a   ->  commit

    git check-ignore -q docs/cli      ->  ignored, absent from the archive
    git check-ignore -q docs/_build   ->  ignored, absent from the archive
    code_index_meta.json              ->  untracked, absent from the archive

The extraction and the two runs were executed by the campaign's driving agent and
independently reproduced by `entrypoints-engineer`, who reached the same 6 real and 18
unmeasurable. This record verifies the mechanism behind the classification rather than
re-running the suite: the inputs the 18 failures read are confirmed gitignored or untracked at
HEAD, so their absence from an archive extraction is systematic rather than incidental.

Both runs were intersected rather than one being trusted, which is the plan's own standing
requirement for this lane after an earlier count moved 19 to 28 on peer churn.

## Notes

**The classification is what makes the 6 trustworthy; the count alone would not.** The 18
non-real failures fail because the extraction lacks what they read — generated
`docs/cli/*.rst`, `docs/_build/html`, `code_index_meta.json`, and `.git` itself for two tests
that shell out to `git ls-tree` and `git ls-files`. **A `git archive` run measures committed
SOURCE state, not committed REPOSITORY state**, and that gap is a property of the instrument
rather than a defect in the tree.

**A false finding was nearly reported from this run and the near-miss belongs in the record.**
Six terminology-resolution tests were red at extracted HEAD — the same six that `P03`'s
terminology row closed as green in the working tree. That is precisely the signature of a
masked green: red at HEAD, green locally, in a row already closed. The executor was one step
from reopening it.

They fail because the generated CLI reference sources they resolve against are gitignored, so
the extraction cannot contain them. **Counting before classifying would have produced a
confident, wrong story about a row that is fine.** The method note worth carrying: on this
instrument a red is not evidence until you have asked what the extraction is missing, because
its absences are systematic and predictable rather than random.

**On the qualification that produced this row.** The campaign-close review flagged the earlier
"26 down to 6" as measured on a dirty tree while this row sat open demanding a clean one. The
outcome is that **the qualification was correct and the number was also correct** — 6 both
times. Those are not in tension. A measurement can be right and still not be entitled to
assertion, and the remedy was to earn the entitlement rather than to defend the figure. Had
the clean measurement returned 20 real, the caution would have prevented a false claim; that
it returned 6 does not make the caution unnecessary, it makes it cheap.
