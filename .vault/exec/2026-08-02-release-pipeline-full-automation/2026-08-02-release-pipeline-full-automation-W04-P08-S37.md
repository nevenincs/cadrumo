---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:08c5da6785a39d712a02ad9b82d2b06894466b2ef80f070716872269687f1e36'
step_id: 'S37'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Comment on tracking issue 618 with the true split naming the repository half landed 2026-07-27, the two environments already deleted, the third pending OP-12, and the index-side Trusted Publisher registrations that no agent can verify, then close it once its forge half is complete, carrying any surviving index-side registration forward as a named operator item rather than silently absorbing it, gate: gh issue view 618 shows the comment and the closed state, flagged forge-side and non-local, and the carried-forward operator item is named in the runbook operator-actions section which the runbook conformance test asserts is present

## Scope

- `RELEASING.md`
- `src/cadrumo/tests/test_release_config.py`

## Description

Measured the live forge (`gh api repos/nevenincs/cadrumo/environments/{pypi,pypi-data-manuals,pypi-data-official}`) before writing anything: `pypi` and `pypi-data-manuals` confirmed 404 (deleted), `pypi-data-official` confirmed still present with `required_reviewers` + `branch_policy`. Confirmed `.github/workflows/pypi-upload.yml` and `dev/release/tests/test_pypi_upload_workflow.py` are both absent from the tree (deleted at commit `e9e5acceb9`, 2026-07-27). Posted the true-split comment on issue #618 (repository half complete; forge half two-of-three done, `pypi-data-official` pending OP-12; index-side PyPI Trusted Publisher registrations for all three retired projects unverifiable by any agent) and closed the issue. Broadened RELEASING.md's OP-12 paragraph (landed in S36) to name the carried-forward index-side check across all THREE retired projects rather than just `pypi-data-official`'s own registration — deleting a GitHub environment does not delete PyPI's separate Trusted Publisher entry. Added `test_releasing_doc_operator_actions_section_names_the_outstanding_halves` to `test_release_config.py`, asserting the Operator actions section (bounded to the next heading, so an unrelated mention elsewhere can't satisfy it by accident) names OP-9, OP-12, and the `#618` carried-forward item.

## Outcome

`gh issue view 618` confirms the comment (https://github.com/nevenincs/cadrumo/issues/618#issuecomment-5159076027) and `state: CLOSED`. Gate green: `uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q` — 9 passed (8 pre-existing + 1 new).

## Notes

INCIDENT (self-caused, fixed same session): this Step's commit (`accaebda18`) was landed via `git commit -m ... -- RELEASING.md src/cadrumo/tests/test_release_config.py` AFTER a deliberate `git apply --cached` had staged only my 40-line addition to `test_release_config.py`, excluding a concurrent peer's uncommitted `bootstrap_sha` schema+test WIP on the same file. Per the `pathspec-commit-takes-working-tree` hazard, `git commit -- <pathspec>` re-sources the WORKING TREE content for those exact paths rather than committing the already-correct index, so the peer's `bootstrap_sha` WIP was swept into this commit under my message despite the careful staging (58 insertions landed, not the intended 40; verified via `git show --stat HEAD`, a check I had skipped for this commit). No data was lost — the swept content was itself correct and necessary — but it left HEAD's `release-please-config.json` missing the `bootstrap-sha` key the now-committed test required, breaking `test_release_please_config_is_well_formed` at a clean checkout. Fixed immediately in a follow-up commit (`66077fd536`) landing the peer's still-uncommitted one-line JSON value, restoring a consistent HEAD; verified via `git show HEAD~0:release-please-config.json` and a fresh pytest run. Lesson applied for the remainder of this dispatch: after any `git apply --cached`, verify the actual COMMITTED content via `git show --stat HEAD` immediately after committing, not just the pre-commit staged diff — S38's commit was checked this way and landed clean (2 files, 37 insertions, no entanglement).
