---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:22b4f55720aa6b1bacea89f75d572d650c048d535b9da5cd23105cc7ed9b804c'
step_id: 'S85'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Fix every leak and residue file the census finds, adding teardown where a test lacks it rather than widening an isolated root's lifetime to paper over the leak

## Scope

- `src/cadrumo/tests/`

## Description

- Fix the systemic root cause found under `S84`: add a helper to the shared collection-root cleanup module that closes and detaches only the root-logger file handler writing under the root about to be removed, called before the existing `shutil.rmtree`, so the file lock is released before deletion is attempted rather than relying on a later, unrelated session's stale sweep.
- Add a real-behaviour regression file for the fix: one test demonstrating the OS-level lock directly (an open `RotatingFileHandler` blocks removal until released, platform-conditioned since POSIX permits unlinking an open file), one test proving the release step alone unblocks a second, ordinary removal without disturbing a sibling root's handler, and one test driving a real subprocess through the actual registered cleanup and the real `atexit` LIFO ordering, since an in-process call cannot substitute for exercising that ordering.
- Fix each of the three individual `tempfile.mkdtemp()`-with-no-cleanup sites the census's structural reading found (all in `integration`-marked files, so absent from the default unit lane and not caught by the `S84` unit-lane run itself): two verdict-file probes in one guard test file switched to the `tmp_path` fixture; one shared helper in a second guard test file switched to writing beside the caller's own `tmp_path`-owned directory instead of minting its own; a subprocess probe in a third file that set its own storage root via a bare `mkdtemp()` inside the spawned interpreter, threaded through as a `tmp_path`-owned directory supplied by the two calling tests instead.
- Verify each fix individually in a dedicated, single-owner sandbox before landing, confirming zero residue after a real run.
- Recover from an unrelated incident: two of the four individual fixes were lost when an in-flight, unrelated over-broad revert loop overwrote peer changes under the same directory before the first commit landed; re-authored both identically once discovered via a HEAD content check, verified again, and committed immediately.

## Outcome

**Systemic fix, verified at scale.** The `-n0` case now produces zero residue on every run tested, including a trivial minimal reproduction that previously left its root behind 100% of the time. Under real `-n auto` multi-worker load the fix eliminated the previously-universal failure down to one non-reproducible-by-the-fix residual per full run, and that residual was diagnosed (not assumed clean) via temporary instrumentation as a worker killed rather than torn down — a process whose `atexit` hook genuinely never ran, not a defect in the release step. The instrumentation left no trace in the committed file.

**Four individual leaks fixed, all confirmed by empirical before/after diff in dedicated sandboxes:** two `verdict.json` probes and one shared helper's write target now use the caller's `tmp_path`; one subprocess-spawned storage root now threads an outer `tmp_path`-owned directory through instead of self-minting one inside the child interpreter. All touched files pass their own suites and the project's mock/monkeypatch/skip/tautology policy gates cleanly after the fixes; the two failures the policy-gate run reported were both in files this work never touched.

**Zero repository-tree and platform-user-data-root leaks**, per `S84`'s census.

## Notes

- Two of the four individual fixes were destroyed mid-session by an unrelated, over-broad revert loop in the shared worktree before they had reached a commit, and were not part of the recovery commit that rescued other in-flight work in the same directory at the time. Discovered only by re-checking `HEAD` content against the expected fix before reporting completion; both were re-authored from scratch, re-verified, and committed immediately under an explicit pathspec to avoid a repeat.
- The "widen the isolated root's lifetime" anti-pattern this Step's own wording warns against was never applicable here: every fix routes a test onto a location a real production accessor or fixture already owns (`tmp_path`, an outer caller's directory), rather than extending any root's retention window or adding a sweep.
