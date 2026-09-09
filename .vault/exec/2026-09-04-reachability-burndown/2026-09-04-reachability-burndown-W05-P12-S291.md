---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a0fe3a1cfefb5a093c14a758528ce212314fdbea4fb78cafa9184acf47368244'
step_id: 'S291'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unconsumed output-classification policy vocabulary and its test-only table census; retain live CLI redaction behavior and persisted-policy resolution gates.

## Scope

- `classification policy models/table`
- `redaction behavior and enrollment tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/core/classification/policies.py`
- `M` `src/cadrumo/core/classification/__init__.py`
- `M` `src/cadrumo/core/tests/test_redaction.py`
- `M` `src/cadrumo/core/tests/test_redaction_rule_enrolment.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "OutputSensitivityClass|OutputClassificationPolicy|default_output_policy_for|_DEFAULT_OUTPUT_POLICY_TABLE" src dev` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/classification/policies.py src/cadrumo/core/classification/__init__.py src/cadrumo/core/tests/test_redaction.py src/cadrumo/core/tests/test_redaction_rule_enrolment.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/tests/test_redaction.py src/cadrumo/core/tests/test_redaction_rule_enrolment.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
