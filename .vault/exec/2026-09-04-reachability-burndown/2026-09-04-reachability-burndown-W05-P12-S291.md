---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:ccc7e0b1d97c414c4fb96a61b12b945e890719cce449006185dff7dac7f0c415'
step_id: 'S291'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
