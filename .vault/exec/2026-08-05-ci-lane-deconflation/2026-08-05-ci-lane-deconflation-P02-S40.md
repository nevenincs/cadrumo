---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:70b0354afb8649346bcc996d4fe838ea2579221d7943bb9eadbd825b069a71da'
step_id: 'S40'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Give the four correctly-integration-marked conformance gates a lane that exists, by adding an integration step to the per-push workflow or by re-marking them unit where they can be. The gate audit found a cause distinct from a wrong marker. These four carry pytest.mark.integration correctly for what they are, and the per-push workflow runs no integration step whatsoever, so the marker is valid and the lane is absent. The default lane pins unit and the only integration invocation lives in a workflow that is dispatch-only, which means these gates have never run on any push at any revision. The four are the rule-surface conformance gate under agent tests, the status-frontend gate under the CLI config tests, and the self-referential-string and suggestion-command conformance gates under the CLI tests. The suggestion-command one is the sharpest instance because it asserts which command an operator is told to run, so while it does not execute a regression there degrades operator guidance silently. Decide per gate whether it genuinely crosses layers or was marked integration by habit, because re-marking a gate that really is integration would buy a green by making it run in the wrong lane

## Scope

- `pyproject.toml and .github/workflows/ci.yml and the four named gate modules`

## Description

- Locate the four named gates and confirm each carries `pytest.mark.integration` plus `pytest.mark.hex_entrypoint` alone (no `serial`, `perf`, `external_tool`, `os_keychain` or `resident_service`).
- Confirm, via `src/cadrumo/tests/test_lane_reachability.py`'s own model, that "declared and CI-invoked" already covers all four (the dispatch-only full lane's broad integration selection reaches them) and that the row's actual gap is a different axis: no *automatically-triggered* lane runs them.
- Add a `test-per-push-integration-gates` justfile recipe naming the four modules explicitly and excluding every marker this repository ever pairs with `integration`, so a future path addition cannot silently pull in a test the lane cannot satisfy.
- Wire the recipe into `ci.yml`'s `cadrumo-static` job as a new step.
- Run the four gates for the first time under this selection to measure whether they are clean.
- Land the step non-blocking against the measured backlog, naming the release condition, rather than either hiding the backlog or blocking every push on it.
- Pin the new step and the recipe's substance in `dev/ci/tests/test_ci_workflow.py`, mirroring the existing `test-dev-ci` pin.
- Add a tracked follow-up Step that owns re-measuring and flipping the flag once the named condition is met, rather than leaving the obligation to a workflow comment nobody greps.

## Outcome

**This row closes on ENROLMENT, not on the four gates being blocking.** The four gates now have an automatically-triggered home: `ci.yml`'s `cadrumo-static` job runs `just test-per-push-integration-gates` on every push, scoped to exactly the four named modules. Re-marking any of them `unit` was rejected, per the row's own prior measurement that all four genuinely cross architectural layers — the fix is a lane, not a marker change. What this row does NOT deliver is a blocking gate: the step carries `continue-on-error: true`, so a red in these four still cannot fail a push today, which is the exact property `P02.S41` and `P02.S42` exist to remove from other steps. Enrolling a fifth non-blocking step would net the campaign zero on that axis if the obligation to make it blocking were left implicit, so it is carried forward explicitly as `P02.S49` rather than closed silently here.

Landed non-blocking because the FIRST real execution under this selection is itself a backlog measurement, not a known-clean confirmation: 6 of 48 selected tests failed (2 in the status-frontend gate, 4 in the suggestion-command gate). The failures concentrate in CLI action-rendering and disposition-census modules (`_modelo_work_runs_cli.py`, `_modelo_work_verification_cli.py`, `_overview.py`, `_overview_rendering.py`, `_tty.py`, `_harness_tools.py`, `_tools.py`) that recent commit history shows an active, in-flight refactor touching (`refactor(cli): sharpen refusal-builder return types`, `refactor(cli): centralize typed action rendering`, `refactor(cli): replace exception recovery suggestions`). Blocking the per-push lane on that backlog would have reddened every push for a defect this row did not introduce and does not own.

The workflow comment states the release condition as a conjunction, not a single milestone: the flag flips off only once BOTH the named refactor lands AND a re-run measures 0 of 48 failing, because either alone is insufficient evidence the backlog is genuinely closed rather than transiently green. `P02.S49` is the tracked Step that owns taking that measurement and performing the flip; this row does not presume its outcome.

This row is `S44`'s flip half and does not close independently of it: `S44` closed the fail-open FX door first, so this new automatically-triggered lane cannot silently escalate a contained, dispatch-only live-service dependency into a per-push external call. The lane this row adds never reaches the FX-dependent modules `S44` found (they live in `entrypoints/cli/tests/test_ledger_*` and are not among the four named paths here), so the two rows' work does not overlap, only order.

## Verification

Workflow YAML parses and the structural conformance gate passes:

    python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
    pytest -q -m integration dev/ci/tests/test_ci_workflow.py
    34 passed in 3.85s

First real execution under the new selection, the backlog measurement:

    pytest -q -n 4 -m "integration and not serial and not perf and not external_tool and not os_keychain and not resident_service" <the four named modules>
    6 failed, 42 passed in 111.16s

Lane-reachability and marker-integrity gates confirm no regression from the new recipe/step:

    pytest -q -n 4 src/cadrumo/tests/test_lane_reachability.py
    24 passed in 32.08s

`ruff check`, `ruff format --check` and `ty check` pass on every touched file.

## Notes

The 6-test backlog is left unfixed by design: `git log` on the affected modules shows an active, uncommitted-at-measurement-time refactor in flight, and this campaign's own established discipline is to route a discovered red to its owner rather than absorb or silently sweep it. The workflow comment names the affected files so the next reader does not have to re-discover the attribution.

THE LANDING HAPPENED, AND THE ENROLMENT CARRIED ONE DEFECT THAT A LATER PASS FOUND AND CLOSED. The work described above is committed as `0c4b5cff25` ("feat(ci): enroll four conformance gates on the per-push lane"), authored by the executor whose record this is; the lock it waited on cleared. Verified independently rather than assumed: the recipe's selection collects exactly 48 tests over the four named modules, matching the figure both this record and the workflow comment state, and the lane-reachability gate stays green.

The defect: the enrolled step delegated to a recipe whose worker count resolves through `{{pytest_workers}}`, whose default is `auto`. This repository forbids `auto` on these runners — the machine's 24 logical CPUs are shared with co-resident runners from other repositories — and `dev/ci/tests/test_machine_aware_load.py` enforces it by resolving each workflow line THROUGH the recipe it calls, substituting the caller's env prefix. With no prefix, the substitution yielded `auto` and `test_ci_pytest_invocations_carry_explicit_worker_counts[ci.yml]` reddened. Measured at HEAD before the fix, and again after, so the attribution is not inferred: the failure appeared with the enrolment and disappears with the pin, while the other 107 tests in that directory are unmoved.

Fixed in `f11b68b88b` ("fix(ci): pin the per-push integration-gates worker count to 8") by pinning `CADRUMO_PYTEST_WORKERS=8` on the calling line — the split the unit job already uses, which keeps the recipe's workstation-friendly default while CI states its own machine-aware size. Eight also matches the `test-dev-ci` step immediately above it in the same job.

    pytest -q -n0 -m "unit or integration" dev/ci/tests src/cadrumo/tests/test_lane_reachability.py
    2 failed, 108 passed in 23.45s

The two remaining failures are peer surface, not this row's, and are named rather than absorbed: `test_no_workflow_anywhere_uses_actions_artifact_storage` reports 19 sites across `packaging-claude.yml`, `packaging-homebrew.yml` and `packaging-scoop.yml` (owned by the artifact conversion in `79597c0197`), and `test_every_workflow_with_an_off_lane_job_carries_the_watchdog` reports `ci-runner-probe.yml`'s `hang-windows` job (owned by the merged runner-probe branch). Neither test reads `ci.yml` or the justfile, and neither file is touched by this row.

This step's diff (`.github/workflows/ci.yml`, `justfile`, `dev/ci/tests/test_ci_workflow.py`) was clean and unentangled — `git diff` on each showed only this row's own additions — so it landed as a direct `git commit -- <paths>` per the worktree-safety protocol, no apply-cached drive needed. It was blocked for several hours by an orphaned `.git/index.lock` (unchanged size and mtime for the duration, diagnosed as a dead holder rather than live contention, confirmed independently by the team lead, who found no process on the host with a start time anywhere near the lock's); nothing under `.git/` was touched while waiting. The lock cleared on its own, and `0c4b5cff25` landed shortly after.
