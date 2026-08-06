---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:bbf3864b2fff24274a6fb4bf02a2d6d608f6521dd0f0fd4c18bdc6f6ff90a2cb'
step_id: 'S21'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Author the release orchestrator workflow shell taking a dry_run boolean and an optional resume input naming an existing packaging-smoke run and nothing else, with no typed confirmation input because the dispatch itself is the intent act, running on the self-hosted fleet under a product-scoped no-cancel concurrency group so two dispatches cannot interleave two versions, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes pinning the exact input set, the runner labels, the concurrency group and its cancel-in-progress false, and asserting no confirmation-phrase input exists

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/release/tests/test_release_orchestrator_workflow.py`

## Description

- Author the orchestrator shell with exactly two inputs, `dry_run` and `resume_packaging_run_id`, on the self-hosted fleet under a product-scoped no-cancel concurrency group.
- Add the `preflight` job resolving the dispatch into a plan and emitting `resume` and `dry_run` as outputs every downstream stage keys on.
- Record in the header why there is no confirmation input and why the workflow is not push-triggered.
- Add six conformance tests.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q` reports 6 passed, and the repository CI gates in `dev/ci/tests` report 14 passed, so the new workflow satisfies the self-hosted-fleet and change-class gates.

## Notes

`dry_run` defaults to `true`. The asymmetry decides it: defaulting to a real release makes an accidental press of the Run button irreversible, while defaulting to a rehearsal costs one extra dispatch. This is a slightly stronger default than the plan text required and is worth the friction.

The confirmation-input assertion matches input NAMES by pattern rather than against an allowlist, so a future `confirm_publish` or `type_yes_to_continue` reds without anyone remembering to extend a list. The same shape as the promoter's window-shortening guard, and for the same reason: an allowlist only catches the additions someone thought of.

The input set is pinned as exact equality rather than a subset. Every additional input is a decision moved out of code and onto a form where it is neither validated nor recorded.

## Precondition check (the drift I flagged before starting)

Ran the HEAD check on the three W02 module surfaces before authoring, and it found real drift the plan could not have anticipated. `dev/release/version_bump.py` and `dev/release/run_resolution.py` are pure library modules: neither declares `main()`, an argparse parser, nor a `__main__` guard, and their only consumers are their own tests. The plan's S22 and S23 gates say the orchestrator "invokes dev.release.version_bump" and "invokes dev.release.run_resolution", which as written means a `python -m` invocation that does not currently exist.

The P03 author clearly anticipated this caller - `commit_tag_and_push` documents that "the orchestrator passes push=True only inside CI" - so the intent is settled and only the entry point is missing. S22 and S23 will therefore each add a `main()` to the module they wire, which is additive, changes no existing signature, matches the package's own pattern (`soak_promoter`, `environment_inventory`, and `evidence_release` all expose one), and satisfies the plan's gate text literally rather than by reinterpretation. Both modules' Steps are closed and committed, so this is not an edit against in-flight work. Flagged to the coordinator as a scope deviation, since those two files are outside the declared scope lists of S22 and S23.
