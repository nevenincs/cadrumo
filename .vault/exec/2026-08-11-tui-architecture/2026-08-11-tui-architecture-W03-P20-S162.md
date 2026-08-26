---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:7fa2da483971c6c0f2ec585c684fab1ea3d8c1096a49f21fcf48ce106e01e821'
step_id: 'S162'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Expose the canonical ProjectionModeloReadiness native atomic capture, owner generation, and neutral opaque comparison domain without inferring capability, collapsing readiness axes, or duplicating operator-state computation

## Scope

- `src/cadrumo/application/state_projection.py and focused readiness parity/currentness tests`

## Changes

- `M` `src/cadrumo/application/state_projection.py`
- `M` `src/cadrumo/application/tests/test_state_projection.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `M` `src/cadrumo/tests/registry_revision.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py`
- `M` `src/cadrumo/entrypoints/cli/tests/_modelo_review_package_support.py`
- `verify:` `pytest test_state_projection.py -k readiness_capture -n0` -> `pass`

## Notes

Three call sites still passed `registry_revision_id=` to
`law_selected_revision_for_work_target` after the W03.P20.S174 rename, because
that sweep's replacement pattern did not match the `registry_revision_id=None`
formatting. The regression was introduced by S174 and is corrected here in
`tests/registry_revision.py`, `test_config_preflight_revision_default.py` and
`_modelo_review_package_support.py`.

The capture calls the sole `_build_modelo_readiness` producer and republishes
its records whole; no axis is collapsed and the capture carries exactly
`reports`, `comparison_domain` and `generation`, so no capability is inferred
from a readiness verdict. The owner observation composes the active profile
pointer, a digest of the profile record and the registry authority's own
current-coordinate generation.
