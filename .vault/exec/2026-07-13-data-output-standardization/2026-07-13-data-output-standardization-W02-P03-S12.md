---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

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
