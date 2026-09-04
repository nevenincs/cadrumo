---
tags:
  - '#audit'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:c850a501f1ae825e96ed2b660d6c1034ca9cbb7793f2f68f601db32ee664d242'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# `cli-distribution-consolidation` audit: `test suite cost`

## Scope

Whether the packaging test suites are slow because the work is large or because
they are degraded. Measured on this Windows host with real runs, not estimated.
Two independent passes agreed on every figure quoted here.

## Findings

### test-suite-cost | critical | The packaging tests copy the entire development environment, twice per test

`_client_venv_template` in the distribution-evidence test module resolves the
launcher under test with `shutil.which`, takes the venv that contains it, and
copies the whole thing. That venv is the project's own development environment:
4.4 GB across 52,351 files, carrying `torch` at 2.9 GB, plus `playwright`,
`transformers`, `scipy`, `basedpyright` and the built data package. The tests
need two console-script launchers from it.

The copy costs 60 s cold. Eight call sites in that one module then each take a
second, hardlinked copy of the 46,005-file template into their own temporary
directory, at 32.6 s measured warm. One test alone, run in isolation, takes
2 m 15 s and passes; the module stacks roughly five minutes before the other
fifty-seven files in the directory are reached. What was read as a hang is this
cost accumulating serially.

### test-suite-cost | high | The template is cached per process and never deleted

The cache is a `functools.lru_cache` over a bare `mkdtemp` with no finalizer, so
every fresh pytest process pays the full cold copy again and leaves another
4.2 GB behind. Twelve orphaned template directories were measured on this host,
totalling **46 GB**, dated across two prior sessions.

### test-suite-cost | high | A two-minute filesystem test runs in the fast lane

The module is marked `unit`, so it collects in the default quick-feedback lane.
The comparable Homebrew and Scoop suites, which do less filesystem work, are
correctly marked `integration` and `serial` and are excluded from that lane.

### test-suite-cost | medium | Part of the local cost is the dirty worktree, and is not a CI cost

The commit-defined build root falls back to `git archive` plus extraction when
the tree is dirty: 24.9 s to produce a 274 MB archive and 45.4 s to expand its
39,092 files. This worktree is permanently dirty because it is shared, so the
fallback always fires locally and never fires on a clean CI checkout. The
mechanism throughout these measurements is file **count** against NTFS per-file
overhead, not byte volume, so none of these figures should be carried over to a
Linux runner.

### test-suite-cost | low | Two suites did not reproduce their reported slowness

`dev/ci/tests` and `dev/release/tests` were reported at roughly 80 s and five
minutes; both measured under 50 s in isolation. Host contention in this shared
worktree is the likeliest explanation, but it was not reproduced, and is
recorded as unexplained rather than guessed. Both passes also observed
pre-existing failures and collection errors in `dev/ci/tests` unrelated to
performance.

## Recommendations

Build a minimal client venv from the two already-built wheels rather than
copying the ambient development environment; this removes the 4.4 GB source
entirely and makes the remaining copies cheap enough that the caching question
mostly disappears. Give whatever template survives an explicit finalizer, and
reclaim the 46 GB already orphaned. Reclassify the module as `integration` and
`serial` so a multi-gigabyte filesystem test stops collecting in the fast lane.

The measured degradation answers the standing question directly: the packaging
suites are slow because of a defect in how a fixture obtains its environment,
not because the work they do is large.
