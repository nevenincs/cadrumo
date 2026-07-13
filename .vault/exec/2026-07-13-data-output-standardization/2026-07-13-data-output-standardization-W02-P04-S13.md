---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S13'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace data-output-standardization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
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
     The Author the structural lifecycle gate asserting every settings dir field declares exactly one lifecycle class and ## Scope

- `src/cadrumo/core/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the structural lifecycle gate asserting every settings dir field declares exactly one lifecycle class

## Scope

- `src/cadrumo/core/tests`

## Description

- Author a structural lifecycle gate that enumerates every `_dir`/`_path`/`_root` Path-typed Settings field (31 today) and partitions them into five declared classes: ROTATION, TTL, RETENTION, UNBOUNDED_BY_DESIGN (each with a stated reason), and EXEMPT_INPUT.
- Assert the classification is complete (no unclassified field), carries no stale names, and is pairwise disjoint (exactly one class per field).
- Assert every non-exempt output directory derives from the state root (is in `_STATE_ROOT_DERIVED_DIRS`) or is an opt-in `None`-default override - so a new field with a concrete `PROJECT_ROOT`-anchored default fails the gate.
- Pin `cadrumo_usage_ratios_path` as the single-file output it is (unbounded-by-design, still root-derived).

## Outcome

The settings output surface now has a structural gate that forces every new directory field to declare a growth lifecycle and to root under the storage root, closing the wave-1 review's MEDIUM finding. Gates: the lifecycle gate (4 tests) passes; ruff clean. Classification today: rotation = cadrumo.log; TTL = status cache; retention = LLM cache/usage/run-telemetry, run traces, registry disk cache (count-eviction), wallet dumps; unbounded-by-design = the encrypted substrate (token/secret/blob/audit), filing artefacts (submissions/drafts/justificantes/filing-history/workflow-runs/inbox), financial catalogues, backups, parity store, usage-ratios file, and the corpus-text cache file; exempt = the two bundled corpus roots, the IVA catalogue root, the operator certificate path, and the storage-root container.

## Notes

`workflow_runs` was classified unbounded-by-design after confirming its persistence layer has no prune/rotation (the earlier axis-1 research note calling it a "rotation store" was imprecise - the cited `_rotation.py` is master-key rotation, unrelated). The corpus-text cache is unbounded-by-design because it is a single content-fingerprinted JSON file bounded by the finite bundled-corpus source set, not a growing directory. Final step of Wave W02 (lifecycle policy).
