---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:4011eb249da38b659001f21733569cde494033ec82706472ba43a40f2339fd74'
step_id: 'S69'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Enforce and prove canonical tax-fact temporal coverage, date-axis selection, provenance, and refusal outside source-grounded windows

## Scope

- `dev/registry/compiler/fact_validation.py`, `dev/registry/compiler/validator.py`, and `dev/registry/tests/test_retired_fact_provider_gate.py`

## Changes

- `M` `dev/registry/compiler/fact_validation.py`
- `M` `dev/registry/compiler/validator.py`
- `A` then `R` `dev/registry/tests/test_migrated_legal_parameter_fact_gate.py` to `dev/registry/tests/test_retired_fact_provider_gate.py`
- The mandatory compiler and `RegistryValidator` catalogue gates reject missing, temporally uncovered, ungrounded, or retired-provider facts with no bypass.
- `verify:` `uv run pytest -q dev/registry/tests/test_catalogue_verification_catalogues.py dev/registry/tests/test_administrator_retention_authored_facts.py dev/registry/tests/test_retired_fact_provider_gate.py` -> `19 passed`
- `verify:` `uv run ruff check dev/registry/compiler/fact_validation.py dev/registry/tests/test_retired_fact_provider_gate.py` -> `pass`
