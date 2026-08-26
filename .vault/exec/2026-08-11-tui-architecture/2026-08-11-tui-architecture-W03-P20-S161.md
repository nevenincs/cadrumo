---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5c23bb497494a5b8e6be4f662019c2b01eddbea54dc43c8e2b92ab4112217310'
step_id: 'S161'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Hard-move the bounded ModeloWorkReview contract, its sole build_modelo_work_review semantic join, and its native atomic capture/current-coordinate pair with owner generation and neutral opaque comparison domain into the sole public application/modelo/work_review.py defining module, atomically migrate every production, S126-registration, test, dynamic, and tooling consumer to direct imports and delete work_review_projection.py plus every package binding, while proving exact complete-review parity without reconstructing any field, retaining a parallel assembler, or introducing a shim, alias, fallback, bridge, or re-export

## Scope

- `src/cadrumo/application/modelo/work_review.py`
- `retired src/cadrumo/application/modelo/work_review_projection.py`
- `src/cadrumo/application/modelo/__init__.py inert-namespace gate`
- `every affected production/S126-registration/test/dynamic/tooling consumer`
- `and focused complete-parity/currentness/direct-import tests`

## Changes

- `R` `src/cadrumo/application/modelo/work_review_projection.py -> src/cadrumo/application/modelo/work_review.py`
- `M` `src/cadrumo/application/modelo/work_review.py`
- `M` `src/cadrumo/application/modelo/tests/test_modelo_work_review.py`
- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_review_cli.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_work_review_envelope.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/work_review.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`
- `M` `src/cadrumo/tests/modelo_work_review.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `M` `dev/locales/_fstring_registry.py`
- `verify:` `pytest test_modelo_work_review.py -n0` -> `pass`

## Notes

The currentness coordinate composes the work-unit and calculation catalogue
revisions with a content digest of the verification catalogue. The verification
repository, unlike its two siblings, exposes no `load_revisioned`; adding one
would have reached into another package's persistence adapter and past this
Step's declared file scope, and a digest over the catalogue the review already
loads detects every content change without a second read.

`test_modelo_work_review_envelope.py::test_review_record_round_trips_through_
registered_schema_envelope` is red for reasons outside this Step. A peer's
in-flight `_archive_push_payloads.py` carries a relative-import off-by-one
(`...core` where every sibling uses `....core`) and a doubled rename token
(`ProfileArchivePushPushResult` against a `ProfileArchivePushResult` command
target). Both were left untouched rather than repaired mid-sweep. The other
fourteen consumer tests across both lanes pass.
