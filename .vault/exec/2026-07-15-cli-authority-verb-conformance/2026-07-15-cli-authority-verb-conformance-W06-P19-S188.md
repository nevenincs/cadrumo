---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S188'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run JSON schema registration and output conformance for every live leaf

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

Run JSON schema registration and output conformance for every live CLI leaf.

## Outcome

SATISFIED, with a discrimination caveat recorded below.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`.
Collected 154, 154 passed, exit line `154 passed in 9.65s`, exit code 0, at HEAD `1844ef2ea0`.

## Notes

This suite passed while a live-leaf-to-schema gap genuinely existed, and the gap was caught
elsewhere. The generated-reference conformance gate recorded under S192 found two live leaves,
the profile create and edit verbs, with no schema reachable through the production payload-module
discovery walk. This suite did not surface that.

The two gates are therefore not interchangeable. This one checks registered schemas and their
output shapes; the S192 one is the only surface comparing the LIVE leaf set against the registry.
Reading this green result as proof that every leaf has a schema would be a false green.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
