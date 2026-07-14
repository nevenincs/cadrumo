---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S10'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace honest-all-green with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-07-14-honest-all-green-plan placeholders are machine-filled by
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
     The Make the loader-cache cross-session proof and the import-hygiene scan robust under parallel execution without weakening them and ## Scope

- `parallel-sensitive tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make the loader-cache cross-session proof and the import-hygiene scan robust under parallel execution without weakening them

## Scope

- `parallel-sensitive tests`

## Description

- Reproduce the parallel-suspect set sequentially at HEAD: the loader-cache
  cross-session proof, the lockfile wait test, and the import-hygiene debt
  scan all pass under `-n 0` (30/30), confirming load artifacts rather than
  regressions.
- Diagnose the two genuinely load-sensitive tests: the lockfile wait test
  gave a 0.25s-holding subprocess a 2s acquisition budget, and the
  cross-session cache proof gave each spawned real pytest session (a full
  registry compile) a 60s timeout — both embed idle-machine latency
  assumptions this heavily loaded shared box violates.
- Widen both to hang guards (30s acquisition window; 300s subprocess
  timeout) with comments stating the budget is a hang guard, not a latency
  assertion. Assertion sets unchanged — the proven contracts (waiting
  acquisition succeeds once the holder releases; a second real session
  reads rather than recompiles the shared pickle) are intact.

## Outcome

Both modules green sequentially (19 passed); ruff clean. Commit
`d48805e4dc`.

## Notes

The import-hygiene debt-count scan needed no change: it passes in both
modes on a quiesced tree; its parallel-run failure traces to live peer
edits landing mid-suite in this active shared worktree, which the P06
final verification run re-checks. No invariant was weakened; both edits
are wall-clock-budget widenings on guards that only exist to prevent
infinite hangs.
