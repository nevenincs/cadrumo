---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:16bc94d4e5e231a8d781c5860f5892e0341e088bb03bf79220adf39c1eec3300'
step_id: 'S77'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` execution: `W04.P15.S77`

## Scope

- `src/cadrumo/_data/registry/aeat/categories and src/cadrumo/_data/registry/aeat/facts and dev/registry/compiler/categories.py and dev/registry/compiler/fact_providers.py and dev/registry/tests`

## Changes

- `M` `dev/registry/analysis/facts_wave2_provider_handoff.toml`
- `D` `dev/registry/compiler/categories.py`
- `M` `dev/registry/compiler/fact_providers.py`
- `M` `dev/registry/tests/test_category_holiday_compiler_behavior.py`
- `A` `dev/registry/tests/test_facts_category_profile_retirement.py`
- `D` `src/cadrumo/_data/registry/aeat/categories/profiles.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0065-categories-statutory-cap.toml`
- `M` `src/cadrumo/domain/categories/registry.py`
- `verify:` `uv run pytest -q dev/registry/tests/test_category_holiday_compiler_behavior.py dev/registry/tests/test_facts_category_profile_retirement.py dev/registry/tests/test_facts_wave2_provider_handoff.py dev/registry/tests/test_wave2_fact_provider_handoff.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/categories/registry.py dev/registry/compiler/fact_providers.py dev/registry/tests/test_category_holiday_compiler_behavior.py dev/registry/tests/test_facts_category_profile_retirement.py` -> `pass`
