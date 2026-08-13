---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:1aa5633cef0fff17e1d5d1f19f300c20a1ca49852f2f920fe7097a74b981a113'
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

This step's diff (`.github/workflows/ci.yml`, `justfile`, `dev/ci/tests/test_ci_workflow.py`) is clean and unentangled — `git diff` on each shows only this row's own additions — so the intended landing is a direct `git commit -m ... -- <paths>` per the worktree-safety protocol, no apply-cached drive needed. As of this writing that commit has not happened: `.git/index.lock` has sat frozen (unchanged size and mtime) since before this row's work started, diagnosed as an orphaned lock from a dead holder rather than live contention (confirmed independently by the team lead, who found no process on the host with a start time anywhere near the lock's). It has not been touched. This row's Description and Outcome describe the completed and verified work; the commit landing is the one remaining action, tracked outside this record rather than claimed here in advance of it.
