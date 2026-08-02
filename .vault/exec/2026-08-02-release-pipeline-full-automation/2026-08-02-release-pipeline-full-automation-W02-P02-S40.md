---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:6ee5bf7daf66b6a542da65bc4d2f7ab1b0d9f89752a6e2e1617b7211d2fb5643'
step_id: 'S40'
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
     The S40 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Declare the lane-to-workflow mapping that turns a claimed channel into the acquisition workflow the orchestrator dispatches, covering packaging-scoop, packaging-homebrew, and packaging-claude, and keep it separate from the operator-minted claude row source so the dispatchable acquisition lane and the four non-automatable real-client captures are never conflated into one input, gate: uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs passes asserting each mapped channel resolves to an existing workflow path on disk and that the claude channel resolves to BOTH a dispatchable acquisition lane and a human evidence-release precondition and ## Scope

- `dev/packaging/publication_inputs.py`
- `dev/packaging/tests/test_publication_inputs.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare the lane-to-workflow mapping that turns a claimed channel into the acquisition workflow the orchestrator dispatches, covering packaging-scoop, packaging-homebrew, and packaging-claude, and keep it separate from the operator-minted claude row source so the dispatchable acquisition lane and the four non-automatable real-client captures are never conflated into one input, gate: uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs passes asserting each mapped channel resolves to an existing workflow path on disk and that the claude channel resolves to BOTH a dispatchable acquisition lane and a human evidence-release precondition

## Scope

- `dev/packaging/publication_inputs.py`
- `dev/packaging/tests/test_publication_inputs.py`

## Description

Added `LANE_WORKFLOW_BY_CHANNEL` (channel id → acquisition workflow path: `scoop`→`packaging-scoop.yml`, `homebrew`→`packaging-homebrew.yml`, `claude-plugin`/`mcpb`→`packaging-claude.yml`), `acquisition_lane_workflows()` (resolves `acquisition_lanes()` channel ids to distinct workflow paths, deduped since claude-plugin and mcpb share one dispatch), and `unmapped_acquisition_lanes()` (fail-closed companion: a lane channel with no declared workflow). Kept structurally separate from `SOURCE_INPUT_BY_CHANNEL`/`host_extension_precondition_refusal` (S08) per the plan: a claude channel's dispatchable acquisition lane (proves the plugin/MCPB install mechanism) and its human evidence-release precondition (the four claude-* real-client rows) are two distinct concerns that must never conflate into one input.

## Outcome

Gate green: `uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs` — 30 passed (23 pre-existing + 7 new). Coverage: every `LANE_WORKFLOW_BY_CHANNEL` value resolves to a real file on disk; both claude channels map to `packaging-claude.yml` AND to `claude_evidence_release` in `SOURCE_INPUT_BY_CHANNEL` (the both-lane-and-precondition property S40 mandates); today's descriptor needs no lane workflow; claiming scoop+homebrew resolves to their two distinct workflow paths; claiming both claude channels dedupes to one workflow; a structural completeness test proves every channel `acquisition_lanes()` could ever return already has a lane workflow declared, confirmed dynamically by claiming every channel in the descriptor and asserting `unmapped_acquisition_lanes()` stays empty.

## Notes

No incidents. The shared git index carried unrelated staged work from a concurrent P04 agent (soak_promoter.py, release-soak-promoter.yml) at commit time; the explicit-pathspec commit (`git commit -- dev/packaging/publication_inputs.py dev/packaging/tests/test_publication_inputs.py`) correctly excluded it — verified via `git show --stat HEAD` showing only the two intended files. This closes W02.P02 in full: S05, S06, S07, S08, S40 all landed and checked.
