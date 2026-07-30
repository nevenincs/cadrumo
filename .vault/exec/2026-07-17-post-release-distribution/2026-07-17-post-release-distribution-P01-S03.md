---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-30'
modified: '2026-07-30'
body_schema: 'body-v1'
step_id: 'S03'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# RESOLVED 2026-07-28, run 30391339584 at commit 0b4fba14f9 is green across all five jobs including homebrew-linux-arm64, the SIGILL toolchain defect no longer reproduces, evidence lives as a per-run GitHub draft per the aggregation gap named in the plan Description, no further blocker on this row

## Scope

- `.github/workflows/packaging-homebrew.yml`

## Description

- Query the qualifying Homebrew acquisition workflow run, `30391339584`, through the GitHub Actions API.
- Confirm its source commit, `0b4fba14f9`, is an ancestor of the current `HEAD` via `git merge-base --is-ancestor`.
- Enumerate all five job conclusions on the run and confirm every one is `success`.
- Record that the evidence artefact is the run's own GitHub draft release, not a tracked repository path, because `var/` is gitignored.

## Outcome

Run `30391339584` (`https://github.com/nevenincs/cadrumo/actions/runs/30391339584`) completed with overall conclusion `success` at source commit `0b4fba14f9e30e7dee8d00cc99ebc1c7f97be2bd`, confirmed an ancestor of the worktree's current `HEAD`. All five jobs on the run report `success`:

- `Cadrumo / create evidence draft`
- `Cadrumo / macOS arm64 / Homebrew source install`
- `Cadrumo / Linux arm64 / Homebrew source install`
- `Cadrumo / Linux x86_64 / Homebrew source install`
- `Cadrumo / seal evidence manifest`

The Linux arm64 leg, previously blocked on the argon2-cffi-bindings 25.1.0 SIGILL toolchain defect, is green in this run; the defect no longer reproduces. `P01.S03` is closed on this basis.

## Notes

The evidence for this closure is the run's own GitHub Actions draft release, not a file under this repository's tracked tree: `var/` (where local evidence artefacts would otherwise land) is gitignored, so no local path is retained or citable. Closure therefore cites the run id `30391339584` and its source commit `0b4fba14f9`, queryable through the GitHub API, rather than a repository-relative evidence path.
