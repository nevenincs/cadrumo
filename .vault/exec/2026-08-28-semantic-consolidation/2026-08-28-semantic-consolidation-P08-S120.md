---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:91a62c1adffada12aa2a7ca4ee201bcb3af457541f1a1b845d1acb154a183884'
step_id: 'S120'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Stop the payload gate reading an empty-string presence check as a declared rule, which was flagging a validator that only delegates

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py -n 0 -m ""` -> `pass`

## Notes

The gate excluded `None` and booleans from its threshold test on the grounds
that comparing against either asks whether a field is present. It did not
exclude the empty string, but an optional text field arrives over the wire as
`""` rather than `None`, so `value is None or value == ""` is one presence check
in the two spellings the wire uses. The gate read the second half as a rule and
flagged a validator whose whole body delegates to the canonical usage-ratio
authority.

Loosening a detector risks blinding it, so the change was probed against eight
expressions: `> Decimal("1")`, `< 0`, `== "ES"` and `len(value) > 9` still flag;
`is None`, `== ""`, `is True` and a comparison between two projected fields do
not.
