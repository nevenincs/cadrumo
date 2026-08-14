---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e7d66505e8cafbe12ef08e50d0324e429bd09b09c864a95c3cea4be1091a6dc1'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# `test-harness-sanity` audit: harness performance

## Scope

Measured, not estimated. Every figure below came from running the thing; two hypotheses that looked obviously right were checked and disproved, and both are recorded so nobody spends the afternoon re-deriving them.

The subject is what the harness costs to RUN: collection wall-clock, per-worker fixed cost, and per-test setup. Suite correctness is out of scope here.

## Findings

### import-time-side-effect | fixed | One eager registry load cost 3.2x on collection and 21 modules

A shared test-support module resolved a registry revision id in a module-level constant, so importing it loaded and validated the entire registry authority as a side effect of import. That is paid by every module that imports it, whether or not the importer needs a revision id, and it is paid again by every parallel worker.

It became visible only when this campaign's fixture consolidation repointed four further test modules at that support module for its shared taxpayer persona. Each inherited a full authority load it had no use for, and a latent condition became a collection error that killed the module outright.

Resolved on first use rather than at import: collection errors 21 to 2, and full collection 310s to 98s.

The generalisation is the useful part. Expensive work at module scope is charged to IMPORT, and pytest imports during collection, once per worker, for every module in the transitive import graph. A cached function costs the same on first use and nothing on the paths that never touch it.

An AST sweep of all 5580 first-party modules for module-level calls into the expensive entry points now finds two, both in one module already flagged for other reasons. This class is closed rather than merely reduced.

### per-worker-fixed-cost | open, and not this campaign's | Registry validation is recomputed by every worker

A cold registry authority costs **22 seconds per process**, split roughly 5s compiling the authoring tree and 17s validating it.

The compile half is already shared: a fingerprint-keyed disk pickle lets every worker and every subprocess-spawning test read one compiled tree, deliberately enabled under pytest for the bundled read-only tree and deliberately disabled for mutable or synthetic roots, which can be edited mid-run by the very test that built them. That machinery is correct and working.

The validation half is cached nowhere across processes. The suite runs `-n auto` on a 24-CPU machine with `--dist=loadfile`, so every worker that draws a registry-dependent file pays that 17s independently: as much as **7 CPU-minutes of byte-identical validation per suite run**.

The shape of the fix is already in the tree next door — the validation verdict is a pure function of the same tree fingerprint the compile cache already keys on. This belongs to whoever owns the registry package; it is recorded here rather than attempted, because a cache over a validation gate is exactly the kind of change that is easy to make silently permissive.

### disproved | The bundled-tree disk cache is NOT disabled under pytest

Worth recording because the first measurement said it was, and acting on that would have "fixed" working code.

`is_bundled_registry_root` returned False for what looked like the bundled registry root. The predicate was right and the probe was wrong: the bundled root is the `aeat` directory one level below the path being passed. With the real root the cross-process cache is enabled in production and under pytest, exactly as its docstring claims.

A probe that confirms a suspicion deserves the same scrutiny as one that contradicts it.

### disproved | Widening expensive fixture scope would not help

342 fixtures are function-scoped and 163 of those perform expensive setup, which reads as an obvious optimisation and is not one.

The registry authority caches built snapshots per process in its own map, so a function-scoped snapshot fixture returns a cached object after the first build; the scope costs nothing to widen and gains nothing. The remaining expensive function-scoped fixtures construct real encrypted stores, where a fresh store per test IS the isolation contract, and widening their scope would trade a correctness property for no measured time.

The instinct is right in general and wrong here, and the distinguishing question is cheap to ask: does the thing being built already cache, and is per-test freshness load-bearing?

## Recommendations

- Cache the registry validation verdict against the tree fingerprint the compile cache already computes, in the registry package.
- Keep expensive work out of module scope in test-support modules; resolve on first use. This is the one pattern that multiplies across both importers and workers.
- Re-measure worker count against wall-clock once the tree is healthy. `-n auto` yields 24 workers here, and a high per-worker fixed cost can make fewer workers faster; that comparison is not meaningful while a large fraction of tests fail fast for unrelated reasons.

## Notes

Per-test hot spots were not obtained. Two full-lane runs with `--durations` were killed before the summary prints, and durations measured against the current tree would be distorted anyway: a large fraction of tests currently fail fast on a registry gap unrelated to timing, and a failed test is usually a fast one.

The collection figures above are trustworthy because they do not depend on tests passing.
