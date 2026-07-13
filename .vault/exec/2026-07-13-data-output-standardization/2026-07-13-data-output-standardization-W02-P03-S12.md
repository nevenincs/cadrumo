---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S12'
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
     The S12 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
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
     The Add retention pruning for wallet diagnostic dump files and ## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add retention pruning for wallet diagnostic dump files

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`

## Description

- Add a `cadrumo_wallet_diagnostic_retention_days` Settings field (default 30) as the wallet-dump retention window.
- Add `prune_wallet_diagnostic_dumps(dump_dir, retention_days=None, settings=None)` to the wallet read module: dump files in the opt-in directory older than the cutoff (by mtime) are removed; best-effort, never raises.
- Invoke the prune automatically at the end of `_dump_wallet_diagnostic`, so the opt-in dump directory is bounded whenever it is in use.
- Add real-behavior retention tests (age cutoff, in-window keep, missing-dir no-op, settings default), the env-template entry, and a regenerated env-overrides reference.

## Outcome

The wallet diagnostic dump directory now has a declared retention lifecycle. Gates: the wallet-retention suite (4 tests) and the settings/env-parity + env-reference freshness gates pass; ruff clean.

## Notes

The dump writes fixed-name `<label>-summary.txt` files (bounded by label set and overwritten each capture), so its growth was already bounded; the retention prune cleans summaries that linger once captures stop. Pruning is auto-invoked after each dump (the dump is the sole writer of this opt-in directory), which enforces the lifecycle in practice rather than leaving a never-called method. Dump files are plain on-disk files with no bucket session, so the tests set mtimes directly with `os.utime` and prune under the real clock.
