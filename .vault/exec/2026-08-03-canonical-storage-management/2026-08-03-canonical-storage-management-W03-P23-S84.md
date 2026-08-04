---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:a1bd9f83e915e7969411c01558300dfae7f55113e2f111b9009bd8127a27e2d2'
step_id: 'S84'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Run the commissioned test-cleanup census, snapshotting the repository tree and the platform user-data root before and after a full suite run and diffing both, classifying every surviving file as residue inside an isolated root or a leak outside one entirely, gated by the diff itself rather than by reading test source

## Scope

- `src/cadrumo/tests/`

## Description

- Confirm a quiet baseline before measuring: zero live `aeat` CLI processes and a flat real diagnostic log over an idle window.
- Snapshot the repository tree (`git status --porcelain=v1 --untracked-files=all`) and the real platform user-data root (`%LOCALAPPDATA%\cadrumo`, full file listing with size and mtime) before the run.
- Launch the default unit-lane suite with `TMP`/`TEMP` redirected to a dedicated, single-owner sandbox directory rather than the shared OS temp pool, so any isolated-root residue left behind is unambiguously attributable to this run and not to concurrent fleet activity.
- Re-snapshot the repository tree and the real platform user-data root after the run and diff both against the before-state, separating created-by-this-run entries from pre-existing ones by mtime.
- Investigate one anomaly encountered mid-run: a `cadrumo-pytest-<pid>` isolated collection root survived its own process's exit under `-n0`. Instrument the shared cleanup function temporarily to confirm the mechanism, then remove the instrumentation once the root cause was established.
- Verify the fix (recorded under `S85`) empirically under both `-n0` and real `-n auto` multi-worker load in fresh, single-owner sandboxes, comparing residue before and after the fix.
- Extract what per-test failure identity the suite's own log carried for the 22 reported failures, and check the repo-rootdir `.pytest_cache/v/cache/lastfailed` as an alternate source.

## Outcome

**Repository tree: zero leaks.** The only new untracked entries during the run's window were legitimate concurrent peer work (vault exec records for unrelated features, a properly-placed test file plus its fixtures for an unrelated calculation) — inspected by content, not by name, to confirm they were authored artefacts and not runtime residue. A supplementary mtime-scoped sweep of gitignored paths inside the window found only expected tool caches (`.ruff_cache`, `.vault/data/locks/*`, `uv.lock`) — no test-created-and-abandoned file in a scratch location.

**Platform user-data root: zero leaks.** Eight new `cache/registry/*.pkl` files appeared under the real root during the window. These are not attributable to this suite run: the TMP/TEMP redirect means this run's own registry-cache pickles land inside the dedicated sandbox, never under the real root's `cache/registry/`, and the real mtimes span well past this run's actual duration — confirming they are ordinary, unrelated live (non-pytest) `aeat` CLI activity on the shared box. Nothing appeared under `buckets/`, `keystore/`, or `secrets/`.

**Systemic finding, the headline of this census.** Every `cadrumo-pytest-<pid>` per-process isolated collection root was failing its own `atexit` cleanup on every run, not only after a crash — previously and incorrectly characterised as designed 24-hour retention. Root cause: the stdlib `logging` module registers `atexit.register(logging.shutdown)` at import time, well before this project's own cleanup registers during conftest collection; `atexit` runs callbacks in reverse-registration order, so the project's cleanup fires *before* `logging.shutdown()` closes the `RotatingFileHandler` a live process still holds open under its own root. Windows refuses to delete an open file, and the existing `shutil.rmtree(root, ignore_errors=True)` silently swallowed that failure. The root's cleanup was therefore never actually succeeding at the owning process's own exit; it only ever cleared later, once a *different*, unrelated session's stale-sweep (24-hour threshold) found the same root after the file lock had already been released by process death. This explains why the population of un-reaped roots in the shared OS temp directory reached 2,256+ at measurement time: registration of the cleanup callback is not evidence the callback succeeds.

**Multi-worker verification.** With `-n0` the fix (see `S85`) produced zero residue across every repeated run. Under real `-n auto` load (roughly 15-20 xdist workers), one root survived out of the total, reproducibly across two independent runs. Diagnosed rather than dismissed as noise: temporarily instrumenting the cleanup function confirmed the survivor's process id had *zero* log entries at all from the instrumentation — its `atexit` hook never fired in the first place, meaning the worker was killed rather than torn down (routine under heavy shared-box load, and the exact scenario the pre-existing 24-hour stale sweep already exists to catch). This is not a gap in the fix; the instrumentation was fully removed afterward and the file diffed clean against its committed state.

**The 22 reported failures: 0 named, and the honest reason recorded rather than the crash alone.** The suite invocation used quiet output with no verbosity flag and no report-controls flag, so the progress stream carried no per-test identity at all — pytest only prints failure names and tracebacks in the final FAILURES and short-summary phases, and this run never reached that phase: it terminated in an `INTERNALERROR` (a crashed xdist worker's collection bookkeeping), preceded by a separate `node down: Not properly terminated` event for a different worker. The names were never in the captured log to recover, crash or no crash. The repository-rootdir `.pytest_cache/v/cache/lastfailed` was checked as a free alternate source and found already overwritten by later, smaller verification runs in the same session (it is shared per rootdir, not sandboxed per invocation), so it offered no help either. Per explicit instruction, the 40-minute suite was not re-run to chase these; the deliverable is the census diff, not the failure list.

## Notes

- One process mistake during investigation: while probing a permission anomaly on an unrelated, pre-existing (~3-week-old, empty) `cadrumo-settings-*` temporary directory, a plain `rmdir` run to test permissions actually succeeded and removed that directory. It was empty, unrelated to this run, and not something that should have been touched under the "report, do not delete" instruction for pre-existing residue; no further exploratory deletions were made after noticing this.
- The isolated-root retention finding corrects an earlier "designed 24-hour retention, not leakage" characterisation given during this same investigation. That characterisation was internally consistent with the evidence available at the time (both cleanup mechanisms genuinely are registered, and the stale-sweep threshold genuinely is 24 hours) but conflated registration with execution; only measuring whether the roots actually disappeared at their owning process's own exit — rather than trusting that registered cleanup code runs — surfaced the real defect.
