---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:5453d7c839c63b75de8206c47491b3a4a0368133be6a5f6caca8d941d2514ca5'
step_id: 'S12'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Carry resolved precondition actions in error envelopes and retire default suggestions as authority

## Scope

- `src/cadrumo/core/errors/_registry.py`

## Description

- Replace the free-form error-envelope `suggestion` field with the canonical
  `ResolvedPreconditionAction` wire projection introduced by S11.
- Require callers of `build_error_envelope` and `render_error_json` to pass
  an already-resolved action explicitly; keep core free of guard evaluation,
  catalogue lookup, Click inspection, and application policy.
- Remove `get_error_suggestion` from the public error facade and stop text
  rendering from treating registry defaults or exception strings as executable
  authority.
- Complete the cross-module Pydantic schema lazily at the public facade so the
  action definition remains exact without reintroducing the core import cycle.
- Update the one CLI reader and the MCP transport constructor that still
  dereferenced or constructed the retired error-envelope field.
- Add real production-model tests for public JSON-schema completeness, resolved
  action JSON projection, default/override inertness, and strict rejection of
  the retired field.

## Outcome

The error body now has one typed `action` channel with the same strict
`ResolvedPreconditionAction` definition used by notices. Public
`ErrorEnvelope.model_json_schema()` is complete before any envelope build,
and emitted error JSON carries resolved condition identity, evidence, target
command identity, argument materialization, conditionality, or explicit
no-recovery outcome without prose command authority.

Registry `default_suggestion` values and exception `suggestion` attributes
remain present only as enumerated migration inputs. They are no longer consumed
by core JSON, core text rendering, the modelo bad-parameter adapter, or MCP
transport error construction. S12 does not define the later
registry-to-catalogue projection owned by S28 and does not migrate the nine data
parts owned by S50-S57.

## Verification

`uv run --no-sync pytest src/cadrumo/core/errors/tests/test_envelope.py src/cadrumo/core/tests/test_json_envelope_roundtrip.py -q -n 0`

`30 passed in 3.35s`

`uv run --no-sync pytest src/cadrumo/entrypoints/mcp/tests/test_call_runtime.py src/cadrumo/entrypoints/mcp/tests/test_inprocess_runtime.py -q -n 0 -m integration`

`20 passed in 9.53s`

`uv run --no-sync ruff check src/cadrumo/core/errors/_registry.py src/cadrumo/core/errors/__init__.py src/cadrumo/core/errors/tests/test_envelope.py src/cadrumo/core/json_contract.py src/cadrumo/entrypoints/cli/_modelo_cli_support.py src/cadrumo/entrypoints/mcp/_transport.py src/cadrumo/entrypoints/mcp/tests/test_inprocess_runtime.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/core/errors/_registry.py src/cadrumo/core/errors/__init__.py src/cadrumo/core/errors/tests/test_envelope.py src/cadrumo/core/json_contract.py src/cadrumo/entrypoints/cli/_modelo_cli_support.py src/cadrumo/entrypoints/mcp/_transport.py src/cadrumo/entrypoints/mcp/tests/test_inprocess_runtime.py`

`0 errors, 0 warnings, 0 notes`

`uv run --no-sync pytest src/cadrumo/core/errors/tests -q -n 0`

`1 failed, 52 passed`

The single broader failure is
`test_the_reachable_refusals_needing_a_decision_are_the_reviewed_set`:
peer-added `REFUSED_M303_CARRY_INGRESS` is operator-reachable and absent from
that gate's adjudicated set. The failure is independent of the S12 transport
contract and is preserved as an explicit red boundary.

## Notes

Mechanical reconciliation found no production import of
`get_error_suggestion` and no production dereference of
`ErrorEnvelope.suggestion` or `build_error_envelope(...).suggestion`.
Forty-seven files still call `build_error_envelope`, and nine call
`render_error_json`; their unchanged calls validly project `action=None`
until producer migrations supply typed verdicts.

Planned cutover debt remains explicit: 613 `default_suggestion` declaration
rows across nine registry data-part files, plus fourteen legacy test files that
still assert the removed helper or error-envelope field. Those rows and tests
remain owned by S28 and S50-S57; they are not compatibility authority.

The touched-file format check reports only committed S11-era formatting drift in
`src/cadrumo/core/json_contract.py`; the other six touched files pass the
formatter. No broad reformat was applied to peer-owned content.

No commit was attempted. The execution brief explicitly prohibited Git writes
because this shared campaign had carried a protected stale index-lock incident;
the lock was absent at final inspection, but the no-commit instruction remained
binding.
