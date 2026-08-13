---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:9f570aa88b67c1c61b89fdd8e507a6096bd9091807ed769362983f571824573c'
step_id: 'S57'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# confirm `test_json_schema_conformance.py`'s existing key-parity gate still passes and add a note in its module docstring cross-referencing the new content-pinning test, since the existing gate self-describes as structural-shape-only

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

- Confirm the structural key-parity gate still runs and record its exact current failure signature.
- State in the module docstring that this gate settles command-key ownership and envelope structure, not alias constraint contents.
- Cross-reference the MCP-owned content pin without changing a structural assertion or duplicating the schema contract.

## Outcome

The structural gate currently reports 336 passed and 1 failed. The sole failure is outside this phase: `test_profile_bound_command_populates_active_profile_label` creates a quiet profile without required `--tax-residence-jurisdiction-scope`, so the real CLI refuses it before the active-profile label assertion. This is the earlier configuration-precondition failure signature; the pass count increased with independently landed cases and is remeasured here rather than copied forward.

The docstring note is correct and needs no code change. It states that the structural gate establishes which command owns which registered schema, but does not test `minLength`, `maxLength`, or `pattern`. It points to `entrypoints.mcp.tests.test_identifier_schema_contract_pin`, whose field-level sweep pins those contents for both the CLI owner schema and the actual MCP output schema. A loosening that evades both checks remains a published-contract gap.

## Verification

- `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`: pass.
- `uv run --no-sync ty check src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`: one pre-existing unsound-return diagnostic at line 1147; S57 does not touch that return.
- `uv run --no-sync pytest -m integration src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -q`: 336 passed, 1 failed at the documented profile setup precondition.

## Notes

The live structural-gate failure is a separate profile-setup contract change. It blocks a fully green gate but does not contradict the S57 ownership-versus-constraint clarification.
