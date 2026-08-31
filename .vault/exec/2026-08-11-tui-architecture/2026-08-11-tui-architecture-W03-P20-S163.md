---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:7fc7666122071f94c308986171c07fdf18dd8af6a253da5b9b54a3e39d0ba349'
step_id: 'S163'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Hard-move the canonical registry-closure native atomic capture, owner generation, and neutral opaque comparison domain from application/registry/_closure.py into the sole public application/registry/closure.py defining module, atomically migrate every exact consumer to direct defining-module imports, delete the private module and every application.registry package binding, and preserve the existing closure join without recreating development-only authority or blocker classification

## Scope

- `src/cadrumo/application/registry/closure.py`
- `retired src/cadrumo/application/registry/_closure.py`
- `src/cadrumo/application/registry/__init__.py inert-namespace gate`
- `every affected production/test/annotation/registration/dynamic/tooling consumer`
- `and focused closure parity/currentness/direct-import/zero-remnant tests`

## Changes

- `R` `src/cadrumo/application/registry/_closure.py -> src/cadrumo/application/registry/closure.py`
- `M` `src/cadrumo/application/registry/__init__.py`
- `M` `src/cadrumo/application/registry/_filing_export_coverage.py`
- `M` `src/cadrumo/application/registry/_source_connectivity_coverage.py`
- `M` `src/cadrumo/application/registry/tests/test_closure_models.py`
- `M` `docs/api/cadrumo.application.registry.rst`
- `A` `docs/api/cadrumo.application.registry.closure.rst`
- `D` `docs/api/cadrumo.application.registry._closure.rst`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/registry/tests/test_closure_models.py src/cadrumo/application/registry/tests/test_filing_export_coverage.py src/cadrumo/application/registry/tests/test_source_connectivity_coverage.py -n0` -> `pass`

## Notes

The Step row describes moving a native atomic capture, owner generation and
opaque comparison domain out of this module. The module holds none of those:
it defines the fail-closed closure records only, and the move covers exactly
that surface. The wider `application/registry` suite and the import-hygiene
gate are red on peer surfaces unrelated to closure — modelo private reaches
and an ambiguous registry revision selection — so the verification above is
scoped to the moved contract and its two consumers.

## Follow-up (W03.P20.S167 discovery)

The deferred capture pair surfaced as a real S167 blocker: eight Workspace
contributor kinds each need a native atomic capture, and CLOSURE had none.
Before building one, checked whether closure limbs are a pure function of the
registry snapshot (which would make an independent generation a fiction) or
can move independently (which would make one necessary). The two composers
that build `RegistryClosureLimb` rows —
`compose_source_connectivity_coverage` and `compose_filing_export_coverage`
— both take inputs beyond the snapshot: a separately-loaded census manifest,
an `as_of` date driving calendar-based expiry, corpus byte evidence read from
disk, and live proof-authority checks. Closure state provably moves
independently of the snapshot, so a native generation is real, not fabricated.

Landed `src/cadrumo/application/registry/closure_capture.py`:
`RegistryClosureCapture` / `RegistryClosureCurrentCoordinate` /
`capture_registry_closure` / `read_registry_closure_current_coordinate`,
republishing both composers' limbs with a generation keyed by their combined
content. The closed `temporal_coverage` limb name in `closure.py` has no
production producer; this capture republishes only the two limb kinds that
exist and does not fabricate a third. 6 real tests in
`src/cadrumo/application/registry/tests/test_closure_capture.py`, including
one that demonstrates the independence finding executably (same authority and
census, two `as_of` dates, different limbs and generation).
