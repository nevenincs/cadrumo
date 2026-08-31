---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:f891060b3b2d45cd3a5c8aa11dcc3d0a2e82bc4f551503ab6e0bbb9611a9cb00'
step_id: 'S41'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# NEEDS A RULING before execution: align the eight show leaves onto view, or rule show canonical - not covered by the accepted ADR, whose D2 governs data movement only

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/` (7 command-spec modules, 8 handlers, 8 payload classes)
- `M` `src/cadrumo/application/operator_surface/_help.py`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `docs/how-to/` (2 pages)
- `M` `docs/_sequences/contracts/how-to/` (4 contracts)
- `M` `docs/locales/` (es, ca, hu catalogue refresh)
- `verify:` `dev.locales scaffold --check` -> `pass`
- `verify:` `every documented aeat invocation resolves against COMMAND_SPECS` -> `pass`
- `verify:` `pytest campaign gates + operator_surface/tests` -> `108 passed`

## Notes

The eight `token="show"` values were flipped by exact line number with an
assertion that the line held the token, rather than by substitution. Four earlier
census failures in this campaign came from blanket replaces that could not tell a
rename from a move.

Two surfaces were only caught downstream. The deferred-target check found that
the spec-key replace had also hit two handler STRINGS, leaving `config profile
view` and `config storage view` pointing at functions that no longer existed. And
`operator_surface/_help.py` carried literal `command="aeat config storage show
AREA"` strings beside its translation keys, so renaming the keys alone would have
left the curated help printing three dead verbs to operators.
