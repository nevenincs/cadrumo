---
tags:
  - '#research'
  - '#github-actions'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:ee0e7b78068e3b35ccd1acf3b180abfb54f0584a206ca762e7c65d5df99e8f37'
related: []
---

# `github-actions` research: `GitHub Actions lanes: PR lint, merge gate, release`

Question: how should the 19 workflows under `.github/workflows/` be reduced to three lanes: PR-push lint, a PR merge gate that includes registry validation, and a release lane that also does packaging? The owner's review raised five problems: superfluous definitions, packaging mixed into product lanes, legacy work, no registry merge gate, and overlapping per-push and merge gates. The evidence confirms all five. Nothing gates a merge today. `pr.yml` runs one serial job that mixes lint, types, registry checks and full test suites, and runs again on push to `main`. Six more workflows fire on push to `main`, four of them doing packaging or build work. The release path runs no lint, type or registry gate. Local runs were taken on a shared worktree with other contributors' uncommitted edits, so the counts reflect that tree.

## Findings

### Merge protection is absent

- The `protect-main` ruleset is active with only `deletion`, `non_fast_forward`, `update` and `creation` rules, and the repository admin role can always bypass it. It has no `pull_request` rule and no `required_status_checks` rule. Observed with `gh api repos/{owner}/{repo}/rulesets`.
- Admin bypass plus the update restriction already gives the owner-only direct-push model. What is missing is a required-status-checks rule that names the lint and merge-gate check contexts.
- The repository is owned by a user account. Whether merge queue (`merge_group`) is available for it is unverified.

### Trigger inventory and conflation

| Workflow | Triggers today | Role under the target lanes |
|---|---|---|
| `pr.yml` | dispatch; push to `main` and `audit/ci-20260915` (`pr.yml:12-13`); `pull_request` with default types (`pr.yml:23-24`) | Reshape into lint and merge gate |
| `ci.yml` | dispatch only | Manual copy of `pr.yml`; its only extra is `check-data-format` |
| `ci-full.yml` | dispatch | Mostly a copy of `pr.yml`; builds sdists and wheels (`ci-full.yml:305`, `:327`); most added checks are `continue-on-error` |
| `governance.yml` | push to `main` and PR, path-filtered | Its two steps repeat `pr.yml:92` and `:102` |
| `docs.yml` | push to `main` and PR, docs paths | Not in either lint or merge gate; `docs-build`/`docs-check` also run in `ci-full.yml` |
| `agent-harness-eval.yml` | push to `main`, paths | Post-merge only |
| `python-runtime-compatibility.yml` | push to `main`, weekly cron, dispatch (`:12-25`) | Builds and uploads a release cohort (`:117-144`): packaging work |
| `packaging-quick.yml` | push to `main`, dispatch (`:19-31`) | Packaging outside release |
| `packaging-campaign-trigger.yml` | push to `main`, path-filtered (`:26-34`) | Dispatches `packaging-smoke` from `main` |
| `runner-fleet-health.yml` | push to `main`, runner paths | Runner infrastructure, not the product |
| `code-health-report.yml`, `aeat-corpus-staleness.yml`, `aeat-drift-detector.yml` | dispatch | Not gates; the drift detector sends Clave identity secrets to a runner (`aeat-drift-detector.yml:74-79`) |
| `release-please.yml`, `publish.yml`, `packaging-smoke.yml`, `packaging-homebrew.yml`, `packaging-scoop.yml`, `docs-publish.yml` | release chain (see below) | Release lane |

The same checks run in several workflows:

| Check | Runs in |
|---|---|
| `check-style` / `check-format` | `pr.yml:97-98`, `ci.yml:155-156`, `ci-full.yml:64,71` |
| `check-types` | `pr.yml:106`, `ci.yml:164`, `ci-full.yml:78` |
| semgrep | `pr.yml:110`, `ci.yml:170`, `ci-full.yml:81` |
| `check-registry` | `pr.yml:115`, `ci.yml:173`, `ci-full.yml:84` |
| `check-import-boundaries` | `pr.yml`, `ci.yml`, `governance.yml`, `ci-full.yml` |
| `test-ci-contracts` | four times, counting `ci-full.yml`'s `test-tooling` (`justfile:901`) |
| release-cohort build | `packaging-smoke.yml:406`, `python-runtime-compatibility.yml:121`, `build-packaging-cohort` (`justfile:504`) |

Every job bootstraps uv, `just` and `just setup` separately, about 30 copies. The runner-queue watchdog appears in six workflows (`.github/ci-contract-allow.txt:19-24`).

### Superfluous and legacy definitions

- Fork-PR `if:` guards sit in workflows that have no `pull_request` trigger, so they can never matter: `ci.yml:80,114,237,300`, `packaging-quick.yml:53,107`, `python-runtime-compatibility.yml:40,149`.
- `pr.yml` still carries the audit branch `audit/ci-20260915` (`:13`), the `cache_mode` dispatch input (`:4-11`) and the step that uses it (`:68-71`).
- On `main`, the concurrency groups include the commit SHA, so no two runs ever share a group and nothing is deduplicated (for example `pr.yml:27`).
- `just check-workflows` runs only `dev.actionlint` (`justfile:347-348`), but the `pr.yml:90` step name claims it also checks the CI contract. `dev.ci_contract` runs in no workflow. Run locally it exits 1 with 7 violations.
- Stale entries in `.github/ci-contract-allow.txt`:
  - `:36` refers to "Dispatch the publish workflow"; the real step is "Dispatch release validation" (`release-please.yml:100`).
  - `:106` refers to a step that no longer exists in `publish.yml`.
- `dev/ci_contract.py:8` cites `tests/test_ci_contract_parity.py`, which does not exist.
- `WATCHDOG_JOB_NAME` (for example `packaging-quick.yml:68`) never equals the real job name, so the self-exclusion in `dev/ci/runner_queue_watchdog.py:215,410` never matches.
- `.github/actionlint.yaml:18` declares `labels: []`; it is otherwise comments.
- There is no `.pre-commit-config.yaml`. `prek.toml:48-71` holds the local hook set.

### Lint and type state against the target

| Target check | Current command | Scope | Local result |
|---|---|---|---|
| `ruff check` | `just check-style` → `ruff check .` (`justfile:210-211`) | repo, with exclusions at `pyproject.toml:559-570` | exit 1, 2 issues |
| `ruff format --check` | `just check-format` (`justfile:215-216`) | same | exit 1, 3 files |
| `ty check` | inside `just check-types` → `dev.quality.types` (`dev/quality/types.py:31-34,135`) | project root, all rules at error (`pyproject.toml:985-986`) | exit 1, 65 findings, 12 s |
| pyright strict | basedpyright with `typeCheckingMode = "strict"` (`pyproject.toml:1057`, `dev/quality/types.py:205-212`) | only `domain`, `application`, `core` and `adapters/outbound/llm`, tests excluded (`pyproject.toml:1050-1051`) | exit 1, 21 errors, 29 s |
| (not in target) pyrefly | inside `check-types` | same subset (`pyproject.toml:1031-1041`) | exit 0 |

The repository uses basedpyright, not plain `pyright`, and only on a subset of packages. `ty`, basedpyright and pyrefly run inside one wrapper, so no workflow reports a separate result per tool. The target's zero-findings merge rule is not met on this tree.

### Registry validation options

| Command | What it proves | Local runtime and result |
|---|---|---|
| `python -m dev.registry.conformance valid` (`dev/registry/conformance/cli.py:188`) | Full candidate validation through `compile_validated_authority` (`dev/registry/compiler/authority.py:270`) plus legal-catalogue grounding (`cli.py:113-123`) | exit 0 in 30 s: 58 modelos, 146 revisions; development cache probably warm (`authority.py:278-282`) |
| `python -m dev.registry.conformance runtime-load` (`cli.py:234`) | The published authority loads | exit 0 in 2 s |
| `just check-registry` → `dev.registry.analysis.registry_status --check --json` (`justfile:264-266`); used today by `pr.yml:115` | Validity, oracles, target currency and authority currency (`registry_status.py:116-176`) | exit 1 after 241 s; only `authority_currency` failed, as `stale`, probably because of an uncommitted authority swap |
| `test-registry-conformance` | Conformance test suite | Runs only in `ci-full.yml:287-288`, where it is non-blocking |
| `test-registry` / calculation tests | Registry and calculation tests | Excluded from `test-unit` and `test-integration` (`justfile:736`); run in no workflow |

- Neither of the first two commands references secrets.
- Whether the oracle audit inside `check-registry` uses the network is unverified.
- Cold-cache runtime of `valid` is unverified.
- The ADR must settle which of these defines "the registry validates" for merge, and whether a stale published authority blocks a PR.

### Release lane today

1. A merge to `main` fires `release-please.yml`. It refreshes the release PR and pushes `uv.lock` to that PR's branch with `GITHUB_TOKEN` (`release-please.yml:48-60`). Pushes made with that token start no push or PR runs, so the release PR's final head is never re-gated (https://docs.github.com/en/actions/concepts/security/github_token).
2. Merging the release PR creates the tag and the release (`release-please-config.json:6-7`). The same job then dispatches `packaging-smoke` and `docs-publish` together (`release-please.yml:110-133`), so docs can go live before PyPI.
3. An operator dispatches `packaging-homebrew` and `packaging-scoop` by hand, then `publish.yml` with three run IDs (`publish.yml:3-21`). `publish.yml` checks that each run succeeded, has the right name and ran at the tag commit (`publish.yml:56-82`). It then promotes the cohort from the smoke run, runs smoke across 3 OS × every stable runtime (`:242-283`), and publishes to PyPI through OIDC (`:287-344`).
4. No workflow runs lint, types or registry validation in this chain.

Risks in the current release lane:

- **Checks miss the published bytes.** The per-OS campaign legs rebuild their own cohort (`dev/packaging/campaign.py:616`). Homebrew and Scoop test the campaign-built Linux cohort, not the promoted one (`packaging-homebrew.yml:204-223`, `packaging-scoop.yml:266-293`).
- **Cohort tag is always null.** `packaging-smoke.yml:406` passes no `--source-tag`, so `source.tag` is null (`dev/packaging/release_cohort.py:170-185`).
- **No workflow publishes the Homebrew tap or the Scoop bucket,** although `docs/download.md:98,104` points users at them. `dev/packaging/release_pointer_guard.py` and `acquire_*.py` are exercised only by their own tests.
- **Stale authority files may ship.** The wheel and sdist include every `authority-*.sqlite3` (`pyproject.toml:248,360`). Whether databases other than the current one ship is unverified.
- **Build setup gaps.**
  - `publish.yml:210` calls `uv run --no-sync` without `just setup`.
  - `publish.yml:224` uses bare `python`.
  - `packaging-smoke.yml:382-383` calls `just setup` without installing `just`.
  - Whether these fail on a clean runner is unverified.
- **Human-supplied run IDs.** Homebrew and Scoop must be dispatched at the tag ref, or `publish.yml:66` fails. Nothing automates or documents that.
- **Release trigger on docs-publish is probably dead.** `docs-publish.yml:28` listens for `release: published`, but releases created with the default token do not fire it. The workflow also refuses to run until its deploy role is provisioned (`docs-publish.yml:60-82`).

Candidate shape the evidence supports, not a decision:

1. One release workflow calls the merge gate as a reusable workflow via `workflow_call`.
2. It builds the cohort once, with the tag.
3. It verifies that one artifact everywhere: oracles, campaign, Homebrew, Scoop and the runtime matrix.
4. It publishes in order: PyPI, then tap and bucket, then post-publish acquisition, then docs.

`workflow_call` can only reduce permissions, and environment secrets cannot pass through it, so `publish-pypi` must stay in the caller (https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).

### GitHub trigger mechanics that constrain the target

- **Default PR types.** `pull_request` runs by default on `opened`, `synchronize` and `reopened` (https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).
  - A PR opened on commits that were already pushed never receives `synchronize`, so a required check would never report. The target's "no action on open" conflicts with required checks.
  - Two ways out:
    - Keep `opened` and `reopened`.
    - Trigger lint on `push` with `branches-ignore: [main]`, since checks attach to the commit. Whether GitHub counts those runs toward a PR's required check is unverified.
- **Skipped workflows and jobs.** A required check in a workflow skipped by a path or branch filter stays pending and blocks the merge. A job skipped by `if:` reports success (https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks).
  - The fork guard at `pr.yml:36` would therefore pass a required check without running anything.
  - The docs-only classifier at `pr.yml:57-65` does the same.
- **A distinct merge-gate trigger** is either `merge_group` (merge queue; availability unverified) or required checks on the PR head with "require branches to be up to date" (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).
  - With the second option, running the gate only at merge needs its own event, such as `ready_for_review`, a label, or `pull_request_review`.
  - Without up-to-date enforcement and without CI on `main`, two green PRs can combine into a broken `main`.
- **`release-please` must fire on push to `main`.** The target's "no CI on push to `main`" needs that one exception.

### Contract tests coupled to the current layout

- **Failing today.** 12 selected tests fail on this tree, including:
  - `dev/ci/tests/test_check_set_contract.py:71` and `:124`.
  - `dev/ci/tests/test_python_runtime_compatibility_workflow.py:135,149,164`. These expect a `pull_request` trigger, which contradicts `dev/ci/tests/test_change_class_tiers.py:108-111`.
  - Six tests in `dev/tests/test_lane_reachability.py`.
- **Tied to the current layout; any restructure breaks them:**
  - `dev/ci/tests/test_ci_workflow.py` (`:89-140`, `:524`, `:731`)
  - `dev/ci/tests/test_change_class_tiers.py` (`:121-150`, `:165`, `:174`, `:276`, `:322`, `:365`, `:401`, `:418`)
  - `dev/ci/lane_reachability.py`
  - `dev/packaging/tests/test_packaging_quick_workflow.py`, `test_packaging_smoke_workflow.py`, `test_homebrew_workflow.py`, `test_scoop_workflow.py`, `test_evidence_release_transport.py:57-84`
  - `dev/release/tests/test_publish_workflow.py:135-155`, `test_external_client_release_boundary.py:16`
  - `dev/ci/tests/test_runner_queue_watchdog.py:359,513`
  - `dev/deploy/tests/test_docs_publish_workflow.py:45-67`
  - `src/cadrumo/tests/test_release_config.py:300`
- **Survives a restructure:** `dev/ci/tests/test_action_pinning.py:113`, since every action is pinned by SHA.
- **Also needs updating:** `.github/ci-contract-allow.txt` and `docs/_release_checklist.yaml:18-30`.
- **The cross-run artifact gate can be bypassed.** `dev/ci/tests/test_change_class_tiers.py:322` inspects only `download-artifact` with `run-id`; `gh run download` gets past it.

### Merge-gate cost measurements

These timings come from the Windows workstation (24 logical cores), not the Linux runner. The tree was dirty and about a dozen pytest processes from other sessions ran at the same time, so treat the numbers as rough proxies.

| Check | Wall time | Exit |
|---|---|---|
| `dev.registry.conformance valid`, cold (scratch dev cache) | 158 s | 0 |
| `valid`, warm | 93 s | 0 |
| `runtime-load` | 3 s | 0 |
| `just check-import-boundaries` | 209 s | 1, 39 blocking findings |
| `just check-workflows` | 1 s | 0 |
| semgrep (`pr.yml:110` step) | 410 s | 1, 163 findings |
| harness (`just test-pytest-harness`) | 23 s | 0 |
| `just test-unit 50`, 8 workers | stopped at 15 min, 64 % of 20,347 items; about 23 min projected | stopped |
| `test-integration-parallel` | 561 s, then an xdist worker crashed at 38 % of 5,731 items; about 24 min projected (consistent with `ci-full.yml:31-33`) | 4 |

The failing unit and integration tests reflect this tree and platform, not the suites.

Where the time goes:

- **Registry compiles inside tests.**
  - 42 test modules under `src/cadrumo/adapters/persistence/profile/tests` call `compiled_bundled_authority()`.
  - That call compiles the registry from source, and the cache is per process. Each xdist worker can therefore spend 90–160 s compiling. This is inferred, not measured.
  - The published-authority lease at `src/cadrumo/conftest.py:76` is an existing way to avoid the compile.
- **Slow integration tests.**
  - One fixture takes 220 s: `test_responsive_surfaces.py:71`, which builds an encrypted profile and a full registry inspection per parameter.
  - Workspace inspection tests take 71 s and 53 s.
  - About ten subprocess CLI tests in `test_modelo_work_ux.py` take 17–24 s each.
- **Fragility and dead weight.**
  - `--max-worker-restart=0` (`pyproject.toml:1100`) aborts the whole run when one worker crashes, which makes a required check flaky.
  - Playwright installs two browsers on every run (`justfile:127-128`).
  - The Node setup at `pr.yml:131-135` serves jscpd tests under `dev/`, which `testpaths` does not collect (`pyproject.toml:1081-1084`).
- **No gain from parallel jobs.** There is one Linux X64 runner and it takes one job at a time, so jobs split by concern queue behind each other and each one repeats `just setup`.

Candidate gate within 10 minutes, measured, not decided:

- Lint and types.
- Registry `valid` + `runtime-load` (1.5–2.7 min).
- `check-workflows`, import boundaries and harness: together about 4 min.
- Semgrep only if scoped to the PR diff with `--baseline-commit`.
- Change-scoped unit and integration subsets. These fit only after the per-worker registry compile is removed.
- The full unit and integration suites move to release. The cost: cross-package regressions can sit on `main` until the next release.

### Check and job naming

- **Enforced pattern.** `dev/ci/tests/test_check_set_contract.py:71-110` requires `<Check|Test|Build>: <Subject> [(Linux|Windows|macOS)]`. It also forbids tool or marker words in the subject and requires matrix expressions in the names of matrix jobs.
- **Current violations:**
  - `governance.yml:43`: "Required when applicable: …"
  - `publish.yml:173`: an "Acquire:" prefix
  - `aeat-corpus-staleness.yml:36`: a job with no name
- **Other places that pin names:**
  - `dev/ci/prove_check_set_guards.py:65`
  - job ids in `dev/ci/tests/test_ci_workflow.py:93-98`
  - the "Cadrumo" workflow-name prefix in `dev/ci/tests/test_change_class_tiers.py:371`
  - `.github/ci-contract-allow.txt`, whose entries are keyed as `workflow.yml:Step name`, so step renames break it
- **Watchdog name drift.** `WATCHDOG_JOB_NAME` says "Cadrumo / runner queue watchdog" (for example `runner-fleet-health.yml:87`), but the job is actually named "Check: Runner queue (Linux)".
- **Required checks match by name.** A check and a commit status with the same name must both pass, and a path-skipped workflow stays pending. The docs don't say what happens after a rename or matrix change. Since matching is by name, the old context probably stays expected, but this is unverified. A fixed-name aggregator job with `needs:` on the per-concern and matrix jobs would keep the required context stable.
- **Options:**
  - A: keep the enforced vocabulary with one concern per job, plus a single required aggregator per lane.
  - B: stable lowercase job ids used as names, which requires changing the contract test.
  - C: one required job per lane, with one concern per step.

### `.github/` layout

- **Contents.** 19 workflows, three issue templates, `actionlint.yaml`, `ci-contract-allow.txt` and `ci-control-plane.md`. There are no composite actions and no `workflow_call` workflows.
- **Repeated setup.** 45 jobs contain 44 checkouts, 36 `setup-uv` steps, 26 `just` installs and 28 `just setup` calls. A local composite action under `.github/actions/<name>/action.yml` would replace about 130 of those steps with about 45 references.
  - The checkout must stay in each job, because a local action can only be used after the repository is checked out.
  - `dev/ci_contract.py` rule 2 requires the literal `taiki-e/install-action` pin in every workflow that calls `just`, so that rule would change.
- **Platform constraints** (https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows):
  - Reusable workflows must sit directly in `.github/workflows/`; subdirectories are not supported.
  - Nesting is limited to 10 levels.
  - Permissions can only be kept or reduced.
  - Composite `run` steps must declare `shell`.

### Python support matrix

- **Declared support.** `requires-python = ">=3.13"` (`pyproject.toml:6`), classifiers for 3.13 and 3.14 (`pyproject.toml:20-21`), and `.python-version` pins 3.13.11.
- **Runtime inventory.** `dev/ci/python-runtime-matrix.json` lists cp313 and cp314 as stable and blocking, and cp315 as a non-blocking prerelease `next`. A prerelease row cannot be made blocking (`dev/ci/python_runtime_matrix.py:161`). The phase selection is at `:296-303`.
- **What the probes check today.** Only installed import, CLI and MCP smoke tests (`dev/ci/python_runtime_compatibility.py:1-15`, `:711-760`); no tests, types or registry.
- **Type checker pins.** ty and basedpyright are pinned to 3.13 (`pyproject.toml:982`, `:1053`). Checking types against 3.14 needs a per-run version override.
- **Cost of a 3.13 + 3.14 matrix.** On the single Linux runner it roughly doubles the time of whatever runs in it.

### Self-hosted fleet and platform checks

- **Runners.** `gh api` lists four:

  | Runner | State |
  |---|---|
  | Linux X64 | online |
  | Windows X64 | online; host shared with other repositories (`.github/ci-control-plane.md:21-31`) |
  | macOS ARM64 | offline; runs only on AC power |
  | Linux ARM64 (docker) | offline |

  - `.github/ci-control-plane.md:33` says there is one Linux X64 runner, while `dev/runners/README.md:318-320` describes two; the API lists one.
  - `dev/ci/tests/test_self_hosted_fleet.py:216` requires every job to run on a self-hosted runner.
- **Every Windows and macOS job today is packaging:** `packaging-quick`, `packaging-smoke`, `packaging-scoop`, `packaging-homebrew` and the `publish.yml:154` smoke matrix. `runner-fleet-health.yml:92-124` is runner infrastructure.
- **Platform product tests run in no workflow:**
  - `windows_only` tests of the launcher stubs (`just test-windows`, `pyproject.toml:1155`).
  - `os_keychain` custody tests (`pyproject.toml:1154`), which need an interactive session.
- **Constraints for the ADR.** A required check must not depend on the macOS host. The Windows runner is online and could carry a non-required product check.

### Release-lane review of the draft design

The adversarial review of the draft lanes found these facts:

- **Default-token events start no workflows.** release-please runs with the default token (`release-please.yml:33-36`). Tags, releases and pull requests created with that token start no new workflow runs; only `workflow_dispatch` and `repository_dispatch` do (https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow). Consequences:
  - A release lane triggered by the tag never runs.
  - The release PR never reports PR checks by itself.
  - release-please currently dispatches workflows the draft deletes (`release-please.yml:110-112`, `:130-133`).
- **PyPI trusted publishing is bound to `publish.yml`.** The upload uses `--trusted-publishing always` (`publish.yml:344`), and a trusted publisher is registered against a specific workflow filename. That this repository's PyPI entry names `publish.yml` is inferred, not observed.
- **Current registry checks miss stale authority.** `valid` checks the source and `runtime-load` checks the existing published artifact. A PR that changes registry source without republishing therefore passes both. The `integrity` verb (`dev/registry/conformance/cli.py:322-361`) detects that state.
- **Checks with no new home in the draft.** These run only in workflows the draft deletes:
  - `pip-audit` (`ci-full.yml:340-346`)
  - `check-data-format`, module reachability and docstring references (`pr.yml:116-117`, `ci-full.yml:72`)
  - `docs-check`
  - the serial integration run (`ci-full.yml:199`)
  - packaging performance contracts (`justfile:495`)
  - the future-directive policy (`python-runtime-compatibility.yml:84-86`)
  - every `dev/` test group; `testpaths` covers only `src/` (`pyproject.toml:1081-1084`)
- **Workflow-count floors.** `dev/ci/tests/test_self_hosted_fleet.py:76-77` requires at least 8 workflows and 6 gated ones, and its comment says two sibling modules use the same floor.
- **Semgrep diff mode needs the base commit.** `--baseline-commit` requires the base commit to be present locally. The default checkout is shallow and on the merge ref.
- **Change-scoped selection.** A mechanism exists:
  - Map changed files to their owning `tests/` directories.
  - Widen by reverse imports through `grimp`, which is locked (`uv.lock:1245`).

  Its blind spot is non-Python inputs, which have no import edges: registry TOML, locales, the authority database, `conftest.py`, `pyproject.toml` and `justfile`.
- **Release sequencing.** The tag and release exist before any validation runs, and the cohort seal refuses to reuse a version (`packaging-smoke.yml:385-403`). A partial publication cannot be retried, because `version_identity --scope publish` refuses (`publish.yml:325-334`).
- **Check names from reusable workflows.** A job inside a reusable workflow is reported under its caller job's name. This is widely observed, but the docs pages fetched did not confirm it.
- **A queued job does not fail.** A self-hosted job with no online runner waits in the queue; the time limit was not verified.
- **Per-concern jobs cost setup time.** On one serial runner, about 10 per-concern jobs each repeat checkout and `just setup`.

### What the ADR must settle

1. The lint-lane trigger: `synchronize` only, or also `opened`/`reopened`, or branch `push`.
2. The merge-gate trigger and mechanism: merge queue or required checks with up-to-date enforcement.
3. The merge-gate command set:
   - whether import boundaries, semgrep and actionlint stay (they are architecture gates outside the stated lint list);
   - whether the unit and integration suites stay;
   - which registry command defines "valid".
4. Type-check scope: basedpyright's subset, repo-wide pyright, and whether pyrefly stays.
5. How the current nonzero lint and type findings reach zero before the gate becomes required.
6. The release graph and the exception that lets `release-please` run on `main`.
7. The fate of each workflow in the table above, and removal of the coupled contract tests in the same change.
8. The naming scheme and the required check contexts.
9. The `.github/` layout, including whether to use a composite setup action.
10. The job split by concern, given a single serial Linux runner.
11. The scope of the Linux Python 3.13/3.14 matrix.
12. Where platform (Windows/macOS) checks run.
13. Semgrep scoping.
14. The change-scoped test subset, and removing the per-worker registry compile before it enters the gate.

Not investigated: merge-queue availability on this plan, timings on the Linux runner itself, and the real change-scoped subset runtime.

## Sources

- `.github/workflows/pr.yml:4-13`, `:23-28`, `:36`, `:57-65`, `:90-115`
- `.github/workflows/ci.yml:80`, `:155-173`
- `.github/workflows/ci-full.yml:64-84`, `:287-288`, `:305`, `:327`
- `.github/workflows/python-runtime-compatibility.yml:12-25`, `:40`, `:117-149`
- `.github/workflows/packaging-quick.yml:19-31`, `:53`, `:68`, `:107`
- `.github/workflows/packaging-campaign-trigger.yml:26-34`
- `.github/workflows/packaging-smoke.yml:382-406`
- `.github/workflows/packaging-homebrew.yml:204-223`
- `.github/workflows/packaging-scoop.yml:266-293`
- `.github/workflows/release-please.yml:48-60`, `:100-133`
- `.github/workflows/publish.yml:3-21`, `:56-82`, `:210-224`, `:242-344`
- `.github/workflows/docs-publish.yml:28`, `:60-82`
- `.github/workflows/aeat-drift-detector.yml:74-79`
- `.github/ci-contract-allow.txt:19-24`, `:36`, `:106`
- `.github/actionlint.yaml:18`
- `justfile:210-216`, `:264-266`, `:347-348`, `:504`, `:736`, `:901`
- `pyproject.toml:248`, `:360`, `:559-570`, `:985-986`, `:1031-1057`
- `prek.toml:48-71`
- `dev/quality/types.py:31-34`, `:135`, `:205-212`
- `dev/registry/conformance/cli.py:113-123`, `:188`, `:234`
- `dev/registry/compiler/authority.py:270-282`
- `dev/registry/analysis/registry_status.py:116-176`
- `dev/packaging/campaign.py:616`
- `dev/packaging/release_cohort.py:170-185`
- `dev/ci_contract.py:8`
- `dev/ci/runner_queue_watchdog.py:215`, `:410`
- `dev/ci/tests/test_change_class_tiers.py:108-111`, `:322`
- `docs/download.md:98`, `:104`
- `release-please-config.json:6-7`
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- https://docs.github.com/en/actions/concepts/security/github_token
- Unverified: merge-queue availability for this user-owned repository; whether commit-level `push` checks satisfy PR required checks; cold-cache runtime of `valid`; which authority databases ship in the wheel.
