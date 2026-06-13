---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S64'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W06.P18.S64`

Scope: `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

## Description

- Narrowed the parser error context value before asserting the registry-miss
  message substring.
- Replaced dynamic `**{"año_override": 2026}` construction with the direct
  `año_override=2026` keyword used by the parser contract.

## Outcome

The S64 Declaracion parser boundary bucket is closed. Ty no longer reports the
five diagnostics in `test_parser_boundary.py`, and the two affected parser tests
still pass against the real parser and fixture paths.

## Notes

Verification:

- `uv run --no-sync ty check src/aeat/adapters/inbound/declaracion/test_parser_boundary.py --output-format concise`
- `uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_parser_requires_a_known_registry_model_after_template_resolution src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_parser_extracts_modelo_131_casillas_from_synthetic_fixture -q`
