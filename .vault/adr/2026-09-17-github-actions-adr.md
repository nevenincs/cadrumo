---
tags:
  - '#adr'
  - '#github-actions'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:1b078f2238856d0fe8c7cfb1b4e86f36702ebf72109862e075f2667a7f784b38'
related:
  - "[[2026-09-17-github-actions-research]]"
---

# `github-actions` adr: `GitHub Actions lanes: PR lint, merge gate, release` | (**status:** `accepted`)

## Problem Statement

CI has grown to 19 workflows. Nothing gates a merge. Pull-request checks are mixed with packaging work, legacy definitions and duplicate jobs, and several workflows run again after a merge. The release path verifies no lint, type or registry state. An invalid or uncompilable registry can therefore reach `main` and be published. The repository needs one small set of lanes: fast lint feedback on PR pushes, a merge gate of a few minutes that includes registry validation, and a single release lane that owns all packaging. It also needs stable names that required checks can depend on. Evidence: `2026-09-17-github-actions-research`.

## Considerations

- `main` is already restricted to the owner through the `protect-main` ruleset with admin bypass. The ruleset has no pull-request rule and no required-status-checks rule (research: merge protection).
- A PR opened on commits that were already pushed never receives `synchronize`. A workflow skipped by a path filter leaves its required check pending. A job skipped by an `if:` condition reports success (research: trigger mechanics).
- Measured costs:
  - registry `valid`: 93–158 s
  - import boundaries: 209 s
  - semgrep: 410 s
  - full unit suite: about 23 min
  - full integration suite: about 24 min

  A 60-minute PR check is not acceptable (research: merge-gate cost).
- About 42 test modules may each compile the registry once per xdist worker. That compile cost decides whether any tests fit in the gate (research: merge-gate cost).
- One online Linux X64 runner runs one job at a time. The Windows runner is online. The macOS runner is often offline (research: fleet).
- Supported Python versions are 3.13 and 3.14. 3.15 is advisory and cannot block (research: Python support matrix).
- Required checks match by name. `test_check_set_contract.py` enforces a naming pattern for checks (research: naming).
- There are no composite actions or reusable workflows, and the setup steps are repeated about 130 times (research: layout).
- `release-please` must run on push to `main` (research: trigger mechanics).
- Many `dev/ci`, `dev/packaging`, `dev/release` and `dev/tests` contract tests pin the current workflow layout. Twelve of them already fail (research: contract tests).
- Events created with the default token start no workflow runs, apart from `workflow_dispatch` and `repository_dispatch`. This covers both the tags and releases that release-please creates and the release PR it opens (research: release-lane review).
- PyPI trusted publishing is bound to the publishing workflow's filename (research: release-lane review).

## Considered options

- **Lint trigger.**
  - *Chosen:* `pull_request` with `opened`, `reopened` and `synchronize`. The required check always reports.
  - *Rejected:* `synchronize` only, because it never reports a check for a PR opened on existing commits.
  - *Rejected:* branch `push`. It is unverified whether those runs satisfy the PR's required checks.
- **Merge-gate mechanism.**
  - *Chosen:* required checks on the PR head, plus "require branches to be up to date".
  - *Rejected:* merge queue, because availability for this user-owned repository is unverified.
  - *Rejected:* label or ready-for-review triggers, because they leave the required check pending.
- **Registry proof.**
  - *Chosen:* `dev.registry.conformance valid` plus `runtime-load`.
  - *Rejected:* `just check-registry`, which takes about 4 minutes and bundles oracle and target-currency checks.
  - *Chosen addition:* the `integrity` currency check, run whenever the PR changes registry source or compiler paths. `valid` plus `runtime-load` both pass when a PR changes registry source without republishing the authority, so the currency check closes that gap.
  - *Rejected:* running the currency check on every PR.
- **Test content at merge.**
  - *Chosen:* a change-scoped subset, after the per-worker registry compile is removed. Full suites run at release.
  - *Rejected:* full suites at merge, which take about 47 minutes.
  - *Rejected:* no tests at merge.
- **Semgrep.**
  - *Chosen:* scan only the PR diff at merge, with a full scan at release.
  - *Rejected:* a full scan at merge, which takes about 7 minutes and reports 163 existing findings.
- **Job split.**
  - *Chosen:* on the current single serial Linux runner, one lint job and one gate job, with one step per concern. Every step runs unless the job is cancelled (`if: ${{ !cancelled() }}`), so each concern reports its own result. The per-concern job split becomes a follow-up once more Linux runners exist.
  - *Rejected for now:* one job per concern. That means about 10 serial setup cycles, which breaks the 10-minute budget.
- **Python and platform scope.**
  - *Chosen:* 3.13 is the default interpreter and the merge gate runs on it only. The release lane runs the Linux 3.13 and 3.14 matrix, and Windows and macOS checks run only at release.
  - *Rejected:* the Python matrix at merge.
  - *Rejected:* an optional Windows job at merge.
- **macOS at release.**
  - *Chosen:* macOS is a hard publication requirement. If no macOS runner is online, the release fails; the queue watchdog makes that failure fast. There is no waiver.
  - *Rejected:* macOS as advisory.
  - *Rejected:* a waiver input.
- **Release PR checks.**
  - *Chosen:* release-please runs with a GitHub App token, so its release PR triggers the merge gate like any other PR.
  - *Rejected:* merging the release PR through owner bypass.
- **Naming.**
  - *Chosen:* the enforced `<Check|Test|Build>: <Subject> (<OS>)` vocabulary.
  - *Chosen:* the only required context is a top-level job in the PR-triggered workflow. A job inside a called workflow renders under its caller's name, so it is never required directly.

## Constraints

- Owner-only direct pushes stay on the existing ruleset, whose admin bypass is intentional.
- Every job runs on self-hosted runners (`dev/ci/tests/test_self_hosted_fleet.py:216`). A required check may target only the Linux X64 runner.
- Reusable workflows must sit directly in `.github/workflows/`. Environment secrets cannot cross `workflow_call`, so PyPI publication stays in `release.yml` itself.
- Every action stays pinned to a commit SHA (`dev/ci/tests/test_action_pinning.py`).
- Required checks are enabled only after the current findings reach zero:
  - ruff: 2 issues and 3 files needing format
  - ty: 65
  - basedpyright strict: 21
  - import boundaries: 39
- The type-checker scope is unchanged. "pyright strict" means the repository's basedpyright strict configuration, and ty runs repo-wide.
- pytest `testpaths` collect only `src/` (`pyproject.toml:1081-1084`). `dev/` tests therefore need an explicit home in a lane.

## Implementation

**Three lanes replace the current 19 workflows.**

1. **Merge gate** (`merge-gate.yml`, workflow `Cadrumo Merge Gate`).
   - Triggers:
     - `pull_request` targeting `main`, with types `opened`, `reopened` and `synchronize`;
     - `workflow_call`, with a `full` input the release lane sets.
   - It has no path, branch or job-level `if:` filters. A fork PR fails at step level; it is never skipped.
   - **`Check: Lint (Linux)` job.** Runs `ruff check`, `ruff format --check`, ty, basedpyright strict, pyrefly and actionlint, one step each, each guarded by `!cancelled()`.
   - **`Check: Merge gate (Linux)` job.** Needs the lint job. It fails unless the lint result is `success`, then runs these steps:
     1. Diff-scoped semgrep, before `just setup`, against the fetched PR base commit. With `full`, it scans everything.
     2. Registry `valid` plus `runtime-load`, plus `integrity` when registry source or compiler paths changed (a step-level condition that never skips the job).
     3. Import boundaries.
     4. `test-ci-contracts` whenever `.github/**` or `dev/**` changed. This condition lives inside the step and never skips the job.
     5. The harness step.
     6. The change-scoped test selection.
   - **Change-scoped selection.**
     - Map each changed file to its nearest owning `tests/` directory.
     - Widen the set by reverse imports, using the locked `grimp` import graph.
     - Map non-Python change classes to fixed selections: registry data, locales, the authority database, `conftest.py`, `pyproject.toml` and `justfile`.
     - Add a fixed cross-package contract set.
     - Above a size threshold, the gate records a visible "too broad, deferred to release" advisory instead of silently passing.
   - `Check: Merge gate (Linux)` is the only required context.
   - The target budget is 10 minutes or less on the Linux runner. The Linux runner's setup time and the type-check timings are still unmeasured, so the budget is validated before the rule is enabled.
2. **Release** (`release.yml`, workflow `Cadrumo Release`).
   - `release-please.yml` stays the only push-to-`main` workflow, and it dispatches `release.yml` explicitly. Events created with the default token start nothing else.
   - release-please authenticates with a GitHub App token. Its release PR therefore runs the merge gate, and its dispatch of `release.yml` is explicit. The App's credentials are held as repository secrets; provisioning the App is an owner prerequisite.
   - **Proof phase.** Runs on the release PR head, before any tag exists, so a failure cannot burn a version:
     1. calls `merge-gate.yml` with `full`;
     2. runs the full `src/` unit and integration suites, the serial integration run, registry conformance, the calculation tests, and every `dev/` test group (`test-ci-contracts`, `test-tooling`);
     3. runs `check-data-format`, module reachability, docstring references, `docs-check`, `pip-audit`, packaging performance contracts and the future-directive policy;
     4. runs these on Linux 3.13 and 3.14; 3.15 is an advisory leg;
     5. builds the release cohort once and verifies that artifact: installed-product oracles, the installer campaign, Homebrew, Scoop, and runtime smoke on Linux, Windows and macOS, with one queue watchdog.
   - **Publish phase.** Runs on the release tag and uses the proven cohort, publishing in order:
     1. PyPI;
     2. the Homebrew tap and Scoop bucket;
     3. post-publish acquisition checks;
     4. docs, last.

     Each publish step skips when that exact version and digest are already published, so a partial release can be resumed.
   - `workflow_dispatch` remains for recovery.
   - The PyPI trusted-publisher entry is moved to `release.yml` in step with the rename.

**Shared setup.** A local composite action under `.github/actions/` owns uv, `just` and `just setup`. Checkout stays in each job.

**Deleted workflows.** The following are removed. Every check they held now has a home above.
- `pr.yml`, `ci.yml`, `ci-full.yml`
- `governance.yml`, `docs.yml`, `docs-publish.yml`
- `agent-harness-eval.yml`, `python-runtime-compatibility.yml`
- `packaging-quick.yml`, `packaging-campaign-trigger.yml`, `packaging-smoke.yml`, `packaging-homebrew.yml`, `packaging-scoop.yml`
- `publish.yml`

**Operator-only workflows.** `code-health-report.yml`, `aeat-corpus-staleness.yml` and `aeat-drift-detector.yml` stay dispatch-only or become `just` recipes. None of them is a gate. `runner-fleet-health.yml` leaves this repository's lanes.

**Legacy removed in the same change:**
- the audit branch, the `cache_mode` input and the dead fork guards
- the stale watchdog name
- the stale allow-list entries and the `ci_contract` parity citation
- the dead Node setup

**Contract tests.** Tests pinned to the old layout are rewritten or deleted in the same change, including the workflow-count floors (`dev/ci/tests/test_self_hosted_fleet.py:76-77` and its two sibling modules). `.github/ci-contract-allow.txt`, `.github/ci-control-plane.md` and `docs/_release_checklist.yaml` are updated to match.

**Prerequisites before the rule is enabled.**
- Remove the per-worker registry compile from the test fixtures.
- Relax `--max-worker-restart=0` for the gate selection.
- Bring the lint, type and import-boundary findings to zero.
- Confirm the rendered required-context name on one throwaway PR.

**Branch protection.** The `protect-main` ruleset then gains a pull-request rule and a required-status-checks rule for `Check: Merge gate (Linux)`, with up-to-date branches required.

## Rationale

The owner's lanes separate fast feedback, merge safety and release proof, and each current defect maps to one of them (research: trigger inventory, release-lane review). Required checks on the PR head are the only mechanism verified to work here, and they need `opened` and `reopened` to report at all.

A single required top-level summary is the only context name the platform reliably renders. Its explicit result check closes the loophole where a skipped job counts as passing.

The measured costs rule out full suites, a full semgrep scan and per-concern jobs on one serial runner. Diff-scoped scanning, change-scoped tests and step-level concerns keep the protection within budget.

Proving the build on the release PR before tagging, then publishing the proven cohort idempotently, fixes three release defects:
- the checks never covered the published bytes;
- a failure burned the version;
- a partial publication could not be resumed.

## Consequences

- **Gains.**
  - An invalid registry, a lint or type regression, or a layering violation can no longer merge.
  - No CI runs after a merge except release-please.
  - Packaging runs only at release, against the exact bytes that ship.
  - The workflow count drops from 19 to about five: merge gate, release, release-please and the operator-only workflows.
- **Costs.**
  - Cross-package regressions outside the change scope can sit on `main` until the next release.
  - Releases take hours.
  - The findings cleanup, the fixture compile fix and the change-scope selector are real work before enforcement.
  - Up-to-date enforcement re-runs open PRs each time `main` moves, and those runs queue on one runner.
- **Pitfalls.**
  - An incomplete non-Python change-class map under-tests silently; the size-threshold advisory must stay visible.
  - Renaming the required job breaks protection unless the ruleset changes in the same change.
  - An offline macOS runner fails the release by design, so publication depends on macOS fleet availability.
  - Moving the trusted publisher out of step with the rename breaks PyPI publication.
- **Opens.**
  - More Linux runners allow per-concern parallel jobs without changing the required context.
  - A merge queue could replace up-to-date enforcement if one becomes available.
