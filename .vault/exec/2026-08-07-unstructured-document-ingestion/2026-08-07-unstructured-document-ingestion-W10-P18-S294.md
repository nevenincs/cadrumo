---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:fd3a84d596f70959f6976d2e414644a82c1f247131dee1d540f1cb500117c4d9'
step_id: 'S294'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Retire the seven publish-workflow assertions that still encode the superseded release-asset contract, since they assert the sealed-manifest emit and verify surface that the public-repo artifact-return ADR removed and the job-permission set that predates actions read being added for gh run download - they were invisible while collection aborted and became visible when the module was restored, so they are stale expectations rather than regressions

## Scope

- `.github/workflows/publish-release.yml`

## Description

- Confirm against the governing ADR that the named surface was retired by
  decision rather than lost by regression, before touching any assertion.
- Read the live workflow for what replaced each retired surface.
- Re-express seven assertions against the replacement; retire two that are
  superseded twins of an assertion beside them.
- Mutation-prove every re-expressed assertion from a copy outside the checkout.

## Outcome

Delivered, with the row's premise corrected in TWO ways, both of which change
what the work was.

FIRST, the count is nine rather than seven. Two further assertions in the same
test were invisible until the earlier failures in it stopped aborting: a
releases-API download pattern, and a per-lane evidence-manifest filename.

SECOND, and the one that matters: RETIRE was the wrong disposition for seven
of the nine. The row read them as stale expectations of a removed surface. The
fail-closed leak sweep is not removed - it still runs twice in the publication
job and is the tripwire standing between every attached byte and a leak. Only
the module name changed, when the transport helper shrank to its one live
purpose under the ADR's fourth decision. Retiring those two assertions would
have stopped checking a live safety property while leaving the test names
advertising that it was checked, which is the exact failure mode a sibling row
in this plan names as never-delete.

The verify-verb assertions were the same shape one layer along. That verb was
replaced rather than deleted: because an artifact cannot be attached to a run
that did not produce it, the Actions-API identity assertion IS the binding the
sealed manifest previously had to reconstruct. So the assertions now bind the
identity check - the workflow path and conclusion read back from the API, and
the refusal on mismatch - rather than a verb name.

Two improvements ride along rather than being restorations. The permission
assertion keeps its equality shape, because the property is a ceiling on what
an OIDC-and-contents-write job may also hold, and admits the added read
permission as a consequence of the accepted decision with that reasoning
written beside it. The eleven-row aggregation now proves the run id and the
workflow path are PAIRED at a single call site; two membership checks would
pass with the ids crossed, which is the failure the aggregation exists to
prevent.

Two genuinely retired, both superseded twins of an assertion directly above
them: the releases-API pattern download beside the run-artifact name fetch,
and the per-lane manifest filename no step emits since the drafts went.

## Notes

Mutation proof ran from a scratch copy outside the checkout, with the module's
workflow handle repointed at it, so nothing under the tree was written and no
peer sweep could commit a mutation. Seven mutations, seven reds, and every
mutated test green again against the restored handle: dropping the read
permission, neutering either of the two identity refusals, crossing the scoop
run id onto the homebrew workflow path, renaming the sweep, and moving the
input derivation after the aggregation it authorises.

One mutation initially failed to red, and the reason is worth keeping: the
first pass replaced only the first of the two sweep call sites, so the
membership assertion was still satisfied by the surviving one while the
count assertion caught it correctly. The gate was right and the probe was
wrong, which is the direction that is easy to misread as a weak gate.
