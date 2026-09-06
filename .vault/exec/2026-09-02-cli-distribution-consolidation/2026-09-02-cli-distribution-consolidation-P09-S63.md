---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:4d89782e118458dc2b200127b2c1fd35c4a7c718030b6431d7364887478a31f4'
step_id: 'S63'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Stop a quality sweep from running a repository rewrite when its test module is imported

## Scope

- `dev/quality/namespace_retirement_sweep.py`

## Changes

- `verify:` `pytest dev/quality/tests/test_namespace_retirement_sweep.py -n0 -m ''` -> `pass`

## Notes

The fix was landed on `main` by the concurrent object-name campaign, not by
this Step. What this Step adds is the off-Linux verification the plan required
and no lane had supplied: 13 of 13 pass on Windows, including the two gates
that hold the module inert at import, `test_importing_the_sweep_runs_no_pass`
and `test_importing_the_sweep_does_not_arm_it`.

Independently confirmed rather than read: the module was imported from a
working directory holding no `src/cadrumo` tree, with `--apply` planted in
`sys.argv`. It set `apply=True`, wrote nothing, and left the directory empty.
The rewrite passes are reachable only through `main()` under the
`__main__` guard.
