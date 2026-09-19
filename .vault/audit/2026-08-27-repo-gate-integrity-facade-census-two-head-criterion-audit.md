---
tags:
  - '#audit'
  - '#repo-gate-integrity'
date: '2026-08-27'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:906b14e52685ba7f8be12058e8ed7f1c12c56f114a6b742e9e61b6be930ea331'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `repo-gate-integrity` audit: `the facade census two-successive-heads criterion is unmeetable during active development`

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

## Outcome: the criterion was withdrawn, and the residual drift is serialized

The reviewer withdrew the two-successive-HEADs bar and accepted "green at the
reviewed HEAD, and the safe refresh preserves every adjudication". Their
reasoning is sharper than the argument recorded above and supersedes it: the
bar did not merely become unmeetable, it **measured the wrong property once the
noise was removed**. When it was set, the artefact was 44 per cent gitignored
mirror and 98.6 per cent transitive closure, so a red carried no information
and two green HEADs was a proxy for "this gate is not pure noise". Both
contaminants are gone. A census of live consumers *should* go stale when
consumers change; one that did not would be measuring something other than the
tree.

They also amended their own accepted criterion after it failed in practice: the
safe refresh must be ABLE TO RUN against the current tree, not merely preserve
adjudications when it does. R73 proved the escape hatch could be jammed by the
very drift it exists to absorb.

### Maintenance note: a deleted dependency fails once per layer

Recorded at the reviewer's direction as this pass's own finding, because it is
a stronger claim than the one that retired the bar.

When a peer retires a module a censused row depends on, the census does not
produce one refusal to repair. It produces a chain, and each link is invisible
until its predecessor clears. Observed in order on R73, whose anchored module
was deleted hours after the baseline:

1. `_evidence_text` raised during GENERATION, so `generated_rows()` could not
   complete and `--check` never reached its comparison. `--refresh-reviewed`
   died the same way -- the verb that exists to absorb drift was taken down by
   the drift.
2. With that made instructive, the anchor invariant refused: the re-anchored
   symbol was not among `facade_exported_symbols`.
3. With the absence branch added, the query invariant refused behind it: the
   new symbol did not appear in the historic `rag_query`.

Each layer had independently assumed the dependency existed. None of the three
was visible from the others.

The operational form: after any peer deletion touching a censused module,
expect a chain and drive `--check` to green iteratively. Treating the first
refusal as the whole repair will read as a fix and leave the row broken.

The structural form, worth more than the procedure: `facade_exported_symbols`
conflates symbols a facade REPUBLISHED with symbols the family OWNS. R73's two
were imported from a sibling at the c941 baseline and never defined by the
family at all, so its export list has described a different family than its
surviving owner since the census's first generation. This is the third field
in which that same re-export/definition conflation surfaced -- after
`current_symbol_locators` and `owner_definition_locators`, both fixed at the
locator layer. This one lives in the frozen historic denominator and cannot be
fixed without rewriting history, so it is recorded as a known property rather
than repaired. Two rows are affected and both are correct under the ruling.
