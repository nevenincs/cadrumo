---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:b2a87d220698fd1dedbda2bb2bcca5bfde74b5a40db3631d3305bddc7d23c97d'
step_id: 'S164'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Define in the sole public application/modelo/calculation.py module the calculation-materialization and source-graph-safe native atomic capture/current-coordinate pair, owner generation, and neutral opaque comparison domain by delegating the sole calculation-revision and provenance authorities, atomically migrate every production, S126-registration, test, dynamic, and tooling consumer of that public contract to direct defining-module imports while leaving unrelated package-private calculation services private, and prove exact materialization/provenance parity without a parallel calculation, graph, persistence, or redaction path or any package binding, shim, alias, fallback, bridge, or re-export

## Scope

- `src/cadrumo/application/modelo/calculation.py`
- `src/cadrumo/application/modelo/_calculation_actions.py private implementation collaborator`
- `src/cadrumo/application/modelo/__init__.py inert-namespace gate`
- `every affected production/S126-registration/test/dynamic/tooling consumer`
- `and focused materialization/provenance parity/currentness/direct-import tests`

## Changes

- `A` `src/cadrumo/application/modelo/calculation.py`
- `A` `src/cadrumo/application/modelo/tests/test_calculation_capture.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `verify:` `pytest src/cadrumo/application/modelo/tests/test_calculation_capture.py -n0` -> `pass`

## Notes

`_calculation_actions.py` stays a package-private implementation collaborator:
the new public module delegates to its `get_calculation_revision` authority and
adds no parallel calculation, source-graph, persistence or redaction path. The
capture is source-graph-safe because it republishes the revision exactly as the
authority materialized it; the record already carries its own casilla
provenance, so no separate graph projection is derived.

The surrounding `application/modelo/tests/` suite is broadly red at HEAD (164
failed, 1692 passed on a full sequential run) from concurrent peer work. A
clean-HEAD worktree comparison on the sampled failing modules reproduced the
identical failures, so they predate and are independent of this Step.
