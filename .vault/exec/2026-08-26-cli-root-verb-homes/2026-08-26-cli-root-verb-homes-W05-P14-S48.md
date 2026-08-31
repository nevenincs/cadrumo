---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:288e184a7e79a349fe3006dae0f9349274bdef9aa990e32d4155d3348b35164a'
step_id: 'S48'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Correct the placement gate's docstring, which argued its calculation-signal exclusion from a verb this campaign retired

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_placement_criterion.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_root_placement_criterion.py`
- `verify:` `pytest four campaign gates` -> `22 passed`
- `verify:` `ruff check` -> `clean`

## Notes

The gate explains why a bare `calculation` capability is not an `app` signal by
naming four read-only `config` verbs that declare it. One of the four,
`config profile preflight`, was retired into `app modelo readiness` earlier in
this campaign, so the gate's own justification cited a verb the graph no longer
carries.

The reasoning was never load-bearing on that verb -- the other three carry it --
so the fix is a correction, not a re-argument. The retirement is recorded inline
rather than silently dropped, because a reader comparing this docstring against
an older revision would otherwise wonder which verb went missing and why.

This is the `firmware-reference-parity` failure mode applied to a gate's prose:
a rename or retirement updates the mechanism and leaves the surrounding
explanation asserting the old state.
