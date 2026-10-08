---
tags:
  - '#audit'
  - '#git-free-tooling'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:10a25ffcba17cc6b636ea5221ca616109819a6c23369f814f965414408df0e08'
related:
  - "[[2026-10-07-git-free-tooling-plan]]"
---
# `git-free-tooling` audit: `Repository-owned Git removal and verification`

## Scope

Review of S01-S03 in `2026-10-07-git-free-tooling-plan`, governed by the accepted `2026-10-07-git-free-tooling-adr` and the preserved CI lane, native identity and application distribution obligations. The operator authorized removal of every repository-owned Git executable invocation and Git-calling test. Review covers local tooling commit `015f8a160c`, CI/packaging commit `3aac3b1892`, the S03 enforcement/rule patch and the previously committed plain-assertion configuration `f3c589b358`. Other tasks' concurrent changes are preserved and are not presented as an all-green repository checkpoint.

I used the Vaultspec code-review skill for the integrated review. Current semantic discovery was unavailable; the accepted ADR reads, complete decision listing, feature status and targeted source reads supplied grounding. Developer commands that manage this checkout, external checkout/package-manager implementations and forge REST route names are outside repository-owned executable code.

## Findings

### history-dependent-verification | medium | Git was an unnecessary oracle for local tooling

Resolved. Cleanup used ignored/tracked-file commands; dotenv provisioning discovered other worktrees; local documentation delivery used commit identity; reference helpers extracted archives; native builds counted revisions. The current filesystem and owning inclusion policy now supply cleanup inputs and content labels, explicit source trees supply reference comparisons, and CMake accepts a positive build identifier with development default 1. Automatic worktree-secret discovery and unused archive helpers are removed. Required cleanup protections, exact-path refusal and explicit dotenv source support remain.

Root cause: tools that inspect source content acquired repository history and a process dependency instead. A hung or unavailable executable could stall verification even when the underlying filesystem operation required none of its state.

### defective-git-fixtures | medium | Six tests constructed repositories to prove retired behavior

Resolved. Deleted the Git-backed untracked-file, Git-directory preservation and interrupted-operation tests in `dev/env/tests/test_clean.py`, the two automatic-worktree dotenv tests in `dev/env/tests/test_dotenv.py`, and the revision-count CMake test in `dev/packaging/native/tests/test_cmake_build_number.py`. Their Git setup helper functions are removed. Cleanup tests use ordinary directories and ignore rules; the retained CMake test supplies identifier 2086 and runs with an empty PATH.

Root cause: fixtures installed a version-control dependency and tested the removed implementation rather than the supported content/build contract.

### ci-and-publication | medium | CI shells and smoke fixtures directly invoked Git

Resolved. Change selection and sequence-goldens selection read a supplied repository-relative path manifest; missing metadata selects both gates in full. Invalid or unreadable manifests refuse. The workflow obtains pull-request paths through the forge API, includes rename predecessors, checks listing completeness and event revision identity, and falls back to full selection when the API cap or stale metadata prevents honest narrowing.

Release lockfile, Homebrew formula and Scoop manifest publication use explicit forge API routes and expected existing-file SHA at the captured checkout commit. Existing release version, content, publication-pointer, identity and credential-separation guards remain. New-file updates omit the old SHA so concurrent creation cannot silently succeed as an overwrite. Dispatch calls name the repository explicitly. No remote publication was executed.

Homebrew smoke uses a tap created without repository initialization. Scoop smoke stages the local bucket directory directly. Git setup, commit and pull calls, and explicit Git installation/resolution are removed from packaging scripts. Installation, upgrade, persistence, installed-oracle and cleanup logic remains.

### assertion-rendering | medium | Rich comparison rendering obscured genuine failures

Resolved by the prior `--assert=plain` pytest configuration. The recorded failing layout comparison spent more than 300 seconds inside comparison rendering before a worker was killed; the plain-assertion rerun exposed the same assertion in 0.08 seconds. Assertions remain active. No repository source requests `--assert=rewrite`.

Root cause: automatic structural diff rendering performed expensive matching on a large failed comparison. This is separate from Git invocation and from the underlying layout mismatch.

### executable-call-enforcement | low | The permissive optional-lock guard is replaced

Resolved. `dev/quality/tests/test_no_git_cli.py` replaces `test_git_invocations_take_no_optional_locks.py`. It derives its population from the current filesystem and owning ignore policy. Python calls are parsed structurally, including executable resolution, imports with aliases, keyword arguments and executable paths. Shell, PowerShell, CMake, Rust/C/frontend sources and declared workflow/hook commands receive executable-call checks. Node package scripts are checked separately. Tagged YAML is parsed without constructing objects. Positive fixtures are strings; none executes Git. Required product, tooling, CMake, workflow and frontend owners must occur in the inventory, so an empty or missing-owner population cannot pass.

Compiled binaries, generated outputs and third-party dependencies are not executable source and remain outside this static-call instrument. It detects representative static call forms; it is not a proof about arbitrary dynamically synthesized commands or external tools.

### repeat-dead-code-measurement | low | Product reachability and Vulture remain clean

The fresh working-tree scan reports 3,269 of 3,269 shipped modules runtime-reachable, zero unreachable modules, zero unused-symbol findings and zero orphan tests. It preserves 193 verified data-consumer and 87 development-consumer clearances. Vulture reports zero findings across 3,270 offered Python modules, including its whitelist support file. Evidence: `.logs/git-free-reachability.json` and `.logs/git-free-vulture.json`.

The earlier eleven-module and twenty-declaration populations are historical and resolved in `2026-10-07-dead-code-zero-tooling-coverage-audit`. Python dead-code instruments still explicitly exclude Rust/C/frontend execution, CMake, build outputs and binaries; the broader Git-invocation gate does not turn those exclusions into native dead-code coverage.

### durable-rule | low | The prohibition has an authoritative shared owner

All three codification criteria hold: this is a project-wide never-invoke constraint; it follows the completed S01/S02 execution and passing verification cycle recorded in the accepted ADR and ledger; the 28-rule search found only partial filesystem-inventory coverage, not the absolute executable ban. The partial `00-architecture` rule was extended through `vaultspec-core spec rules edit`, read back through `spec rules show`, and synchronized through the owning CLI. The canonical startup reference and generated Codex/startup copies carry the same body. No installation-owned builtin was changed.

### integrated-review | low | Owned changes pass their applicable checks

PASS for the owned patch. Evidence is fresh to the changed source, tests and configuration. Local-tooling tests: 44 passed in `.logs/git-free-s01-tests.log`. CI, packaging and the initial executable guard: 157 passed in `.logs/git-free-s02-tests-final.log`. Publication contracts, documentation delivery and the expanded YAML guard: 69 passed in `.logs/git-free-guard-and-publication-tests.log`. These runs overlap and are not summed. Final guard population and control results are recorded in `.logs/git-free-executable-call-gate.log`.

Scoped Ruff lint/format and ty pass. Actionlint passes in `.logs/git-free-workflows.log`; all three changed workflows pass their owning YAML data-quality check. Both changed PowerShell scripts parse successfully. The actual CMake input test executed. The publication guard and release transport contract tests passed. Rule/reference parity was checked after CLI synchronization.

One pre-existing CI test still requires the global pytest timeout removed by concurrent work: `test_the_harness_real_proof_outruns_the_default_per_test_wall_ceiling`. The initial run recorded it in `.logs/git-free-s02-tests.log`; the final focused run explicitly excludes this unrelated policy mismatch. The earlier full-unit report still records broader failures in `.logs/full-unit-findings-2026-10-07.md`; it is not superseded by these focused passes.

Actual remote API writes and complete package-manager installs were not performed. Homebrew requires a macOS/Linux host; a complete Scoop smoke requires the sealed release cohort and prepared disposable installation environment. Static workflow/syntax and existing behavioral/contract checks establish the bounded patch, not a completed release installation or publication.

### final-enforcement-census | low | No Git calls in 11,386 executable source files

The final owning gate checked 11,386 executable source/configuration files and found zero Git CLI offenders. All 25 detector, inventory and refusal/acceptance controls passed in 76.01 seconds. The source count includes the two Node package manifests in addition to Python, shell/PowerShell, native/build/frontend and YAML command sources. Scoped lint, formatting and ty passed after the final coverage changes. Canonical architecture rule, canonical startup reference, generated Codex rule and generated startup reference have identical bodies across all four surfaces.

### timeout-policy-follow-up | low | Retired global-timeout requirement is resolved

Resolved by the user's authorized direct follow-up after S01-S03 closure. `dev/ci/tests/test_ci_workflow.py` no longer requires a shared pytest timeout or compares the harness deadline against a workstation-derived default. The renamed test verifies the harness's explicitly requested 900-second deadline and that its collection preflights do not receive that override. The recipe, ordinary correctness-test completion policy, pytest-timeout dependency and plain assertions are preserved. The 2026-10-07 test-completion amendment in `2026-07-20-ci-speed-redesign-adr` governs this correction; no new decision or plan is needed.

All 49 workflow integration tests passed in `.logs/timeout-policy-ci-workflow-tests.log`. The final narrowed correction passed its focused rerun in `.logs/timeout-policy-focused-test.log`; the other 48 test bodies and their inputs are unchanged. Scoped Ruff lint, formatting and ty passed after that correction. Direct review found no remaining in-scope issue. The timeout-policy failure recorded above is historical and no longer outstanding.

## Recommendations

Keep the absolute invocation guard and plain pytest assertions. The timeout-policy mismatch is resolved; keep the harness's explicitly owned deadline independent of shared pytest defaults. Preserve the native/build dead-code scope disclosure and run the existing installation/publication lanes on their designated hosts before claiming live release verification.
