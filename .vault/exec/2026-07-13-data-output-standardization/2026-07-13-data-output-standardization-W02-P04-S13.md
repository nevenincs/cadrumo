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
