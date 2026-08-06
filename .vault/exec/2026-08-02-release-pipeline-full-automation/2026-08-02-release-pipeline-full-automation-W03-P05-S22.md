---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:0d0e4a2ecb185dd69624754001c2d630682f24a8c7ed18b7e1b139cb8157bd31'
step_id: 'S22'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Wire the bump stage as the orchestrator first job invoking the bump executor and emitting the bumped commit and version as job outputs the downstream stages key on, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the bump job invokes dev.release.version_bump and that its outputs are consumed by the campaign stage rather than re-derived

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/release/tests/test_release_orchestrator_workflow.py`
- `dev/release/version_bump.py` (scope deviation, reasoned below)

## Description

- Add `main()` to `dev.release.version_bump`, composing the existing library functions in the retiring checklist's order and emitting the version and commit as workflow outputs.
- Add `_changelog_block_for`, extracting the release body from release-please's own log rather than fabricating one.
- Wire the `bump` job, skipped on a resume, holding the only `contents: write` in the workflow.
- Add three conformance tests.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q` reports 9 passed, `test_version_bump.py` still 23 passed, and `dev/ci/tests` plus the justfile guidance gate stay green, so adding the entry point regressed neither the P03 lane's tests nor the lane gates.

## Notes

### Scope deviation: the CLI the plan assumed

This Step edits `dev/release/version_bump.py`, which is not in its declared scope list. The plan's gate says the bump job "invokes dev.release.version_bump", which as written means a `python -m` invocation - and the module had no `main()`, no argparse parser, and no `__main__` guard. The plan was authored before any W02 module existed, so it could not have known.

Three options existed. Re-implementing the seven-surface bump in workflow YAML would recreate, untested and one layer down, exactly the transcription error class the module exists to remove. Routing through a new orchestrator driver module would satisfy the intent but not the gate's literal text, and would add a second home for logic that belongs with its data. Adding the entry point is additive, changes no existing signature, keeps the module the sole authority over version advancement, and matches this package's own pattern - `soak_promoter`, `environment_inventory`, and `evidence_release` each expose a `main()`.

The P03 author had already anticipated this caller: `commit_tag_and_push` documents that "the orchestrator passes push=True only inside CI". The intent was settled; only the entry point was missing. Their Steps are closed and committed, so this is not an edit against in-flight work, and their 23 tests still pass unchanged.

### Deliberate absences

There is no `--version` flag. A hand-supplied version is precisely the transcription error the bump stage removes, so the CLI can compute a version and refuses to accept one.

`_changelog_block_for` degrades to a bare version heading when release-please's log carries no recognisable body, rather than synthesising entries. A changelog is a claim about what shipped; a thin one is honest and an invented one is not.

`contents: write` is confined to the bump job and asserted absent everywhere else, so the one stage that lands a ref is the only stage that can.
