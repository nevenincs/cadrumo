---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S11'
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
     The S11 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
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
     The Add retention pruning for per-run trace directories and ## Scope

- `src/cadrumo/core/observability/_store.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add retention pruning for per-run trace directories

## Scope

- `src/cadrumo/core/observability/_store.py`

## Description

- Add a `cadrumo_runs_retention_days` Settings field (default 30) as the run-trace retention window.
- Add `prune_run_traces(retention_days=None, settings=None)` to the observability store: enumerate run-id subdirectories under `cadrumo_runs_dir`, remove any whose modification time is older than the cutoff, and return the count removed. Best-effort throughout - an unenumerable runs dir, an unreadable entry, or a failed removal is logged and skipped, never raised.
- Add real-behavior tests: age-cutoff removal, in-window retention, non-run-directory scope exclusion, missing-runs-dir no-op, and the central-settings default.
- Add the env-template entry and regenerate the env-overrides reference.

## Outcome

The per-run trace store now has a declared retention lifecycle rather than accumulating one subdirectory per run forever. Gates: the run-trace retention suite (5 tests) and the settings/env-parity + env-reference freshness gates pass; the full observability suite is 82 passed under sequential (`-n 0`); ruff clean.

## Notes

Age is measured from each run directory's modification time (its last write) rather than a parsed `trace.json` timestamp, so crashed runs that never produced a valid `trace.json` are pruned too instead of accumulating unreadable. Run traces are plain on-disk files with no bucket session, so the tests set directory mtimes directly with `os.utime` and prune under the real clock - no frozen clock is needed or used.
