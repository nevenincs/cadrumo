---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:de074d5429c68d28c2d385515cf5c1ee162e3cac50ebbe907677566f31500636'
step_id: 'S31'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete migrated statutory declarations but retain technical configuration

## Scope

- `src/cadrumo/core/external_constants.py`

## Changes

- `M` `.vault/audit/2026-09-11-facts-registry-s31-external-constants-retirement-audit.md`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `M` `dev/registry/analysis/facts_external_constants_retirement.toml`
- `M` `dev/registry/tests/test_facts_external_constants_retirement.py`
- `M` `src/cadrumo/core/external_constants.py`
- `verify:` `uv run pytest -q -n 0 dev/registry/tests/test_statutory_authored_facts.py dev/registry/tests/test_facts_wave2_provider_handoff.py dev/registry/tests/test_wave2_fact_provider_handoff.py dev/registry/tests/test_facts_external_constants_retirement.py` -> `pass`
