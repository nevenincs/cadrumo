---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:f38bf7736543026a6a1b508ffc1d803e732af3f8ab4054474e08710f6ac57b6c'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `the facade census two-successive-heads criterion is unmeetable during active development`

## Scope

Measured the facade family census against seven unrelated peer commits, to
test the precondition its independent re-review set: green at two successive
HEADs before re-review. Read-only.

## Findings

### The census is now correct, and still drifts

Green at the HEAD where it was refreshed. Red seven commits later:
`registry facade consumer census drifted for
src/cadrumo/domain/calculations/registry/_loader.py`.

The cause is a single genuine change. Diffing stored against generated for
that row, one direct consumer category moved:

    category: test
      added: src/cadrumo/domain/iva/tests/test_provision_window_bounds_grounding.py

A peer added one test file that imports the loader. No commit touched the
loader itself, no symbol locator moved, and the transitive closure is already
excluded from the comparison. The census detected exactly what it exists to
detect.

The authority consumer census drifted over the same span, for the same class
of reason.

### The criterion, not the census, is what fails

The re-review's diagnosis was that the census had no reachable fixed point,
and it was right about the symptom. Two of its causes are now gone: the
gitignored mirror that contributed 44 per cent of the entries no longer
exists, and the tree-wide scalar was removed. What remains is not a defect.

A consumer census records which files import a censused module. In a tree
where seven commits changed 73 Python files, a new importer appears
routinely. "Green at two successive HEADs" therefore requires that no file
anywhere begin importing any of the 78 censused modules between those two
commits -- which asks development to pause, not the gate to be sound.

The bar is measuring tree activity rather than artefact quality.

### Test consumers carry the drift and the least disposition weight

The one drifted category is `test`. A disposition Step acts on production
consumers: whether a symbol has a canonical defining module, and who must be
repointed. A new test importing the module changes nothing about that
judgement, but it reds the gate identically to a new production consumer.

## Recommendations

Do not attempt to satisfy the two-HEAD bar as stated; it is unmeetable while
the campaign is active, and chasing it would mean refreshing the artefact
until the tree happens to be quiet.

Two honest options, for the Step's owner rather than this pass:

- Treat `--check` as a drift DETECTOR whose remedy is
  `--refresh-reviewed`, and re-state S175's precondition as "the check is
  green at the reviewed HEAD, and the safe refresh preserves every
  adjudication" -- both of which now hold and are provable in one run.
- Or narrow the compared categories further, excluding `test` consumers on
  the ground that they carry no disposition weight, and record that exclusion
  with its reason the way the transitive closure already is.

The first is preferable: it changes a criterion that was wrong, rather than
narrowing evidence to fit a criterion. Narrowing to fit is how a gate ends up
proving nothing.

Whichever is chosen, the deciding fact is that the census's remaining drift
is real. Before tonight it could not be read at all, because 44 per cent of
its entries were phantom paths from an interrupted benchmark run.
