---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:3405d62ae9073d6206d16e96ac8b5f7f98f64b78012728cbde23c180d5090cb5'
step_id: 'S10'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Author a per-modelo requiredness capability so the profile schema can express a modelo-scoped required fact without over-demanding it

## Scope

- `src/cadrumo/application/user_profile/`

## Changes

- `M` `src/cadrumo/domain/user_profile/schema.py`
- `M` `src/cadrumo/application/user_profile/preflight.py`
- `M` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `A` `src/cadrumo/application/user_profile/tests/test_preflight_modelo_scoped_requirement.py`
- `verify:` `pytest src/cadrumo/application/user_profile/tests/test_preflight_modelo_scoped_requirement.py` -> `pass`
- `verify:` `pytest src/cadrumo/application/user_profile/tests/test_preflight_reports_unassessed_axis.py` -> `pass`
