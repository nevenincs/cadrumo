---
tags:
  - '#plan'
  - '#github-actions'
date: '2026-09-17'
tier: L2
related:
  - '[[2026-09-17-github-actions-adr]]'
modified: '2026-09-17'
body_schema: body-v2
body_hash: 'sha256:e8c0de9b7bc49ccadfe48c6b47539adda05da6686e25a693732e4a2e20586798'
---

# `github-actions` plan

Replace the 19 workflows with a fail-closed PR merge gate and a single build-once release lane.

## Description

Approved 2026-09-17

**Approval basis.** The owner approved the plan in conversation on 2026-09-17, with these execution constraints:
- **Main worktree only.** All work happens in the main worktree; no separate worktrees.
- **Single committer.** Only the orchestrator runs git and commits. Workers never do.
- **Minimal checks.** Keep check and test runs to a minimum. The orchestrator runs every check, once per change and scoped to the files that change touched. Workers run no uncoordinated or duplicate test suites.

**Model split.**
- Sonnet workers take the mechanical Steps: `P01.S13`, `P02.S01`, `P02.S02`, `P04.S06`, `P04.S19` and `P04.S21`.
- Sonnet workers take `P01.S14` and `P01.S11`, and Opus reviews them.
- Opus workers take `P01.S10`, `P01.S12`, `P01.S15`, `P02.S03`, `P03.S16` to `P03.S18` and `P04.S20`.
- The owner handles the external-action Steps.

**Scope.** Implements the accepted decision `2026-09-17-github-actions-adr`, which governs every Phase. Its evidence is in `2026-09-17-github-actions-research`. No other costly decision is involved.

**What is built.**
- The merge gate: `merge-gate.yml`, the only PR-triggered workflow. Its single required context is `Check: Merge gate (Linux)`, and it runs on 3.13.
- The release lane: `release.yml`. It proves the release PR head on Linux 3.13 and 3.14, builds the cohort once, verifies it on Linux, Windows and macOS (macOS mandatory), and publishes idempotently.
- A release-please workflow that authenticates with a GitHub App token and dispatches the release lane.
- Retirement of the superseded workflows, legacy definitions and layout-pinned contract tests.
- Owner-side enforcement.

**Phase ordering.**
- P01 makes the gate cheap and green before it becomes binding.
- P04 must land in the same change set as the replacement lanes it retires, so no check is left without a home.

**Owner-only external actions.** Some Steps change GitHub or PyPI configuration or need a pushed PR:
- `P02.S04`, the throwaway PR
- `P05.S07`, the GitHub App and its secrets
- `P05.S08`, the PyPI trusted publisher
- `P05.S09`, the ruleset rules

These need explicit owner action or authorization at execution time. Plan approval does not authorize pushing, publishing or changing the ruleset.

**Shared worktree.** The P01 finding counts were measured on a shared, dirty worktree. Re-measure them at execution time and leave other contributors' in-flight edits untouched.

## Steps

### Phase `P01` - Gate prerequisites

Make the merge gate cheap and green: one registry compile per test run, a change-scoped test selector, and zero lint, type and import-boundary findings.

- [ ] `P01.S10` - Remove every dev import from src, moving the affected tests onto src-side published-authority support so no test compiles the registry from dev; `src/cadrumo`.
- [ ] `P01.S11` - Relax the xdist worker-restart limit for the gate test selection; `pyproject.toml, justfile`.
- [x] `P01.S12` - Create the change-scoped test selector with owning-tests mapping, grimp reverse imports, a non-Python change-class map and a visible too-broad advisory; `dev/ci/change_scope.py, dev/ci/tests/test_change_scope.py`.
- [ ] `P01.S13` - Bring ruff check and ruff format findings to zero; `src/, dev/`.
- [ ] `P01.S14` - Bring ty, basedpyright strict and pyrefly findings to zero within the existing scopes; `src/, dev/`.
- [ ] `P01.S15` - Bring import-boundary findings to zero; `src/, dev/`.
- [ ] `P01.S22` - Convert absolute cadrumo self-imports to relative imports inside src/cadrumo and enforce relative-only imports and the no-dev-import rule in the import-boundary gate; `src/cadrumo, dev/quality`.

### Phase `P02` - Merge gate lane

Deliver the single PR-triggered workflow with a lint job and a fail-closed merge-gate job on Linux 3.13.

- [x] `P02.S01` - Create the shared setup composite action for uv, just and just setup; `.github/actions/setup/action.yml`.
- [x] `P02.S02` - Add gate recipes for diff-scoped semgrep, registry valid plus runtime-load plus path-conditional integrity, and the scoped test run; `justfile`.
- [x] `P02.S03` - Create the merge-gate workflow with the lint job, the fail-closed merge-gate job and the full input for workflow_call; `.github/workflows/merge-gate.yml`.
- [ ] `P02.S04` - Prove the gate on a throwaway PR on the Linux runner, confirming the rendered required-context name and the 10-minute budget; `.github/workflows/merge-gate.yml`.

### Phase `P03` - Release lane

Deliver one release workflow that proves the release PR head, builds the cohort once, verifies it on Linux, Windows and macOS, and publishes idempotently.

- [x] `P03.S16` - Create the release proof phase with the full merge gate, full suites and dev test groups on Linux 3.13 and 3.14, release-only checks, and a 3.15 advisory leg; `.github/workflows/release.yml, justfile`.
- [x] `P03.S17` - Build the release cohort once with its source tag and verify it with oracles, campaign, Homebrew, Scoop and runtime smoke on Linux, Windows and macOS, macOS mandatory behind a fail-fast queue watchdog; `.github/workflows/release.yml, dev/packaging/`.
- [x] `P03.S18` - Add the idempotent publish phase for PyPI, the Homebrew tap and Scoop bucket, post-publish acquisition, then docs; `.github/workflows/release.yml, dev/packaging/release_pointer_guard.py, dev/release/version_identity.py`.
- [x] `P03.S05` - Switch release-please to the GitHub App token and dispatch the release workflow; `.github/workflows/release-please.yml`.

### Phase `P04` - Retire old lanes

Remove superseded workflows, legacy definitions and layout-pinned contract tests in the same change set as their replacements.

- [ ] `P04.S06` - Delete the superseded workflows and remove runner-fleet-health from this repository lanes; `.github/workflows/`.
- [ ] `P04.S19` - Remove legacy definitions including the stale watchdog name, stale allow-list entries and the missing ci_contract parity citation; `dev/ci/runner_queue_watchdog.py, .github/ci-contract-allow.txt, dev/ci_contract.py`.
- [ ] `P04.S20` - Rewrite or delete contract tests pinned to the old layout, including the workflow-count floors; `dev/ci/tests/, dev/ci/lane_reachability.py, dev/packaging/tests/, dev/release/tests/, dev/deploy/tests/, dev/tests/test_lane_reachability.py, src/cadrumo/tests/test_release_config.py`.
- [ ] `P04.S21` - Update the CI control-plane and release checklist documentation; `.github/ci-control-plane.md, docs/_release_checklist.yaml`.

### Phase `P05` - Enforcement

Turn on the owner-side external configuration that makes the lanes binding.

- [ ] `P05.S07` - Provision the GitHub App and its repository secrets for release-please; `.github/workflows/release-please.yml`.
- [ ] `P05.S08` - Move the PyPI trusted-publisher entry to the release workflow; `.github/workflows/release.yml`.
- [ ] `P05.S09` - Add the pull-request and required-status-checks rules for the merge-gate context with up-to-date branches to the protect-main ruleset; `.github/workflows/merge-gate.yml`.

## Parallelization

**Can run in parallel** (each has one writer):
- Within P01, `P01.S10`, `P01.S12`, `P01.S13`, `P01.S14` and `P01.S15` touch mostly disjoint areas. `P01.S11` follows `P01.S10`.
- P02 can be drafted alongside P01, since `P02.S01` to `P02.S03` only add new files and `justfile` recipes.
- P03 can be drafted alongside P02, but `P03.S16` depends on `P02.S03`.

**Hard ordering:**
- `P02.S04` needs P01 complete and `P02.S03` landed.
- `P03.S05` needs `P03.S16` to `P03.S18`, plus `P05.S07` for the App token.
- P04 runs after P02 and P03 are proven. `P04.S06` and `P04.S20` land together, because the contract tests fail once the workflows are deleted.
- `P05.S08` lands together with the first release through `release.yml`.
- `P05.S09` is last. It needs P01 at zero findings and the context name confirmed in `P02.S04`.

**Shared files.** The `justfile` and `pyproject.toml` are shared by several Steps, so edits to them are serialized.

## Verification

**Findings are at zero.** Each of these exits 0 on the current tree:
- `ruff check`
- `ruff format --check`
- `just check-types`
- `just check-import-boundaries`

**The per-worker registry compile is gone.** A gate-selection test run compiles the registry at most once.

**The change-scope selector has working detector tests.** They cover a Python change, a reverse-import change, each non-Python change class, and the too-broad advisory.

**The merge gate works on the Linux runner.**
- It passes on a clean PR in 10 minutes or less.
- It fails when a registry fixture is broken, and when a lint violation is seeded.
- It fails closed when any dependency is skipped or cancelled.
- It reports `Check: Merge gate (Linux)` on open, reopen and push.
- It runs `integrity` only when registry or compiler paths change.

**No workflow triggers on push to `main` except release-please.** Confirm by enumerating workflow triggers from the current tree.

**The release lane is proven by a dry run** (dispatch, no publish):
- It builds exactly one cohort, with a non-null source tag.
- Every verification job consumes that cohort.
- A missing macOS runner fails the run quickly.
- Publish steps skip when the version and digest already exist.

**Retirement is complete.**
- Every check listed as homeless in the research has a named Step in the release or merge lane.
- The rewritten contract tests pass under `just test-ci-contracts`.
- `actionlint` and the action-pinning test pass.

**Owner configuration is observed.** `gh api` shows the `protect-main` ruleset with the pull-request and required-status-checks rules. The first real release publishes through `release.yml` with trusted publishing.

**Reviews.**
- Each Phase close gets an integrated review appended to the feature audit, as does plan close.
- Critical and high findings reopen the affected Steps.
