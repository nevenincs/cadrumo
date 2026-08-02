---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:aaccfecc31f2531ac458928283a579cc3d719605c262a41d762a785bc9977f22'
step_id: 'S07'
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
     The S07 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Derive the acquisition lanes a release must dispatch from the same claimed-channel authority publication_inputs and the readiness gate already read, so an unclaimed channel is never dispatched and a claimed one can never be skipped, and so flipping a channel availability to available arms its lane with no workflow edit, gate: uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs passes with cases covering the current descriptor claiming python only, a descriptor claiming scoop and homebrew, and a claimed channel absent from the source mapping refusing rather than passing unproven and ## Scope

- `dev/packaging/publication_inputs.py`
- `dev/packaging/tests/test_publication_inputs.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Derive the acquisition lanes a release must dispatch from the same claimed-channel authority publication_inputs and the readiness gate already read, so an unclaimed channel is never dispatched and a claimed one can never be skipped, and so flipping a channel availability to available arms its lane with no workflow edit, gate: uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs passes with cases covering the current descriptor claiming python only, a descriptor claiming scoop and homebrew, and a claimed channel absent from the source mapping refusing rather than passing unproven

## Scope

- `dev/packaging/publication_inputs.py`
- `dev/packaging/tests/test_publication_inputs.py`

## Description

Added `acquisition_lanes(descriptor)` to `dev/packaging/publication_inputs.py`, derived from the SAME `SOURCE_INPUT_BY_CHANNEL` mapping the publish-dispatch demand (`demanded_inputs`) already reads — no second hand-maintained set. A claimed channel whose evidence source IS the cohort input itself (`python`, whose evidence rides the packaging-smoke run that produced the cohort) needs no acquisition dispatch; every other claimed channel is a lane. A claimed channel entirely absent from `SOURCE_INPUT_BY_CHANNEL` is excluded from the lane set (never silently treated as lane-free) and stays caught by the pre-existing `unmapped_claimed_channels`/`refusals` fail-closed path.

## Outcome

Gate green: `uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs` — 17 passed (10 pre-existing + 7 new). Coverage: today's descriptor (python only claimed) yields zero lanes; claiming scoop/homebrew individually and together arms the corresponding lane(s) with a negative control per channel; reverting availability disarms the lane with no code change; an unmapped claimed channel is excluded from `acquisition_lanes` and still refused by the existing fail-closed path; `python` is never a lane even when every channel in the descriptor is claimed.

## Notes

No incidents.
