---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:d7a568e5b379b0f885e812b12f098220f935ec1d323d627ca245d568ec6a8c86'
step_id: 'S05'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace release-pipeline-full-automation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Build the dispatch-and-resolve module that dispatches one workflow and then resolves the run IT started, keyed on the workflow path, the head commit, and a created-after timestamp captured before the dispatch, refusing on ambiguity rather than guessing, because gh workflow run returns no run id and the smoke workflow queues rather than cancels so the newest run may belong to a neighbour, gate: uv run --no-sync pytest dev/release/tests/test_run_resolution.py -q passes over injected Actions API payloads including a planted competing run started between the dispatch and the poll, and the resolver refuses rather than promoting the neighbour and ## Scope

- `dev/release/run_resolution.py`
- `dev/release/tests/test_run_resolution.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Build the dispatch-and-resolve module that dispatches one workflow and then resolves the run IT started, keyed on the workflow path, the head commit, and a created-after timestamp captured before the dispatch, refusing on ambiguity rather than guessing, because gh workflow run returns no run id and the smoke workflow queues rather than cancels so the newest run may belong to a neighbour, gate: uv run --no-sync pytest dev/release/tests/test_run_resolution.py -q passes over injected Actions API payloads including a planted competing run started between the dispatch and the poll, and the resolver refuses rather than promoting the neighbour

## Scope

- `dev/release/run_resolution.py`
- `dev/release/tests/test_run_resolution.py`

## Description

Built `dev/release/run_resolution.py`: `dispatch_workflow` fires `gh workflow run` (returns nothing, since gh yields no run id). `resolve_dispatched_run` matches the run one dispatch started by workflow path, head commit, the workflow_dispatch event, and a created-after timestamp captured before dispatch. Zero matches raise `RunNotYetVisibleError` (retryable). More than one match raises `RunResolutionError` naming every candidate id — the identify-MY-run hazard, refused rather than guessed. `dispatch_and_resolve` composes both, capturing `created_after` itself immediately before dispatching.

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests/test_run_resolution.py -q` — 26 passed. Coverage includes `test_wait_for_run_refuses_immediately_when_a_competing_run_appears_between_dispatch_and_poll`, which plants a competing run alongside the dispatch's own run in the same poll snapshot and proves the resolver refuses rather than promoting either candidate.

## Notes

No incidents. A pre-commit ruff-format hook reformatted a nested `with` block in the test file after the first commit; landed as a follow-up formatting-only commit.
