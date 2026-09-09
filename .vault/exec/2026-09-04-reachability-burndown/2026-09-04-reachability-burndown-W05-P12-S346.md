---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:249f4fe44aecd303d7210d5a806997cc5d2ec3345fd3a834ebea75f7412d9d3d'
step_id: 'S346'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the residual canonical-helper singularity and enrollment source detectors while retaining owner behavior suites.

## Scope

- `UTC`
- `text-fold`
- `override`
- `FX`
- `CSV`
- `and clock source-policy tests`
- `owner behavior tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_utc_validator_enrollment_inventory.py`
- `D` `src/cadrumo/tests/test_text_fold_enrollment_inventory.py`
- `D` `src/cadrumo/tests/test_override_seam_singularity.py`
- `D` `src/cadrumo/tests/test_fx_stamp_singularity.py`
- `D` `src/cadrumo/tests/test_aeat_csv_normalisation_singularity.py`
- `D` `src/cadrumo/tests/test_canonical_clock_usage.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/time/tests/test_utc.py src/cadrumo/core/tests/test_text_fold.py src/cadrumo/core/tests/test_fold_for_matching_is_canonical.py src/cadrumo/application/invoices/tests/test_fx_conversion_provenance.py src/cadrumo/domain/justificante/tests/test_csv_bound_conformance.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_renta_web_open_safety.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/time/tests` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
