---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6ed4c8a2dde6cec213624563731c7a81c5effce97a3bdbc9237053ee7a37425f'
step_id: 'S163'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
