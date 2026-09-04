---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:1383a6eb937095f982216faf0afa9db94d987d9e0cabd32b381c3f4bd9dec5c6'
step_id: 'S420'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove the RETURN cycle against a changed generation, and retire the in-process CLI-import assertion. INDEPENDENT REVIEW 2026-09-04: W08.P29.S389 claims the installed session returns from every journey, but its tests only build screens from the FIRST generation -- every defect the review confirmed lives in the refresh-and-return cycle against a generation that has since changed, which no test exercises. Add that cycle as a gate. Separately, test_the_installed_session_never_pulls_the_cli_into_the_child_process asserts against the ambient sys.modules of the pytest process and attributes nothing to the code under test; it passes only under loadfile scheduling and fails when run beside its sibling. The subprocess gate in test_installed_entrypoint.py already proves the real property, so the in-process copy should go.

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py`
- `verify:` `pytest -n0 -m '' src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py` -> `pass` (5)

## Notes

The CLI-import gate was probing the wrong surface. The CLI spawns
`-m cadrumo.entrypoints.tui`, which runs `__main__`; the probe imported
`.launcher` alone, leaving `__main__` itself, the shared session protocol and
the whole destination arm unobserved -- and the destination arm is the one most
likely to reach for a CLI helper, because it carries a request across the
process boundary. It is now probed through both invocation shapes, and asserts
each module was actually reached so a probe that stops importing cannot pass by
proving nothing.

Teeth, and evidence the change was not busywork: one CLI import added to
`destination_session.py` pulled in 90+ `cadrumo.entrypoints.cli` modules. The
NEW gate names them and fails. The OLD probe, against the same defect, reports
zero. Restored by copy; 5 passed.

One correction to the finding as filed: the assertion is not order-dependent.
It runs in a fresh subprocess and always could fail for its stated reason -- it
was simply blind to two of the three modules that reason covers.

The generation half of this step (proving the return cycle, not only generation
1) is already carried by the readmit and withdraw gates added with S416:
`test_a_generation_that_gains_a_source_readmits_its_destination` and
`test_a_generation_that_loses_a_source_stops_offering_its_destination`, in
`test_installed_generation_composition.py`, 10 passed.
