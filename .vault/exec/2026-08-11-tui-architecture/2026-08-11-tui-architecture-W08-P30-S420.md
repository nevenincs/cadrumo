---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:d0454c7ba0fb4e55883d21d7cfdcb92353bfbe798dd0e850649b3c4585e1b93e'
step_id: 'S420'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove the RETURN cycle against a changed generation, and retire the in-process CLI-import assertion. INDEPENDENT REVIEW 2026-09-04: W08.P29.S389 claims the installed session returns from every journey, but its tests only build screens from the FIRST generation -- every defect the review confirmed lives in the refresh-and-return cycle against a generation that has since changed, which no test exercises. Add that cycle as a gate. Separately, test_the_installed_session_never_pulls_the_cli_into_the_child_process asserts against the ambient sys.modules of the pytest process and attributes nothing to the code under test; it passes only under loadfile scheduling and fails when run beside its sibling. The subprocess gate in test_installed_entrypoint.py already proves the real property, so the in-process copy should go.

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_no_generated_secret_display.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/tests/test_home_fixtures.py`
- `verify:` `pytest -n0 -m '' tui/tests/test_installed_entrypoint.py test_no_generated_secret_display.py test_home.py` -> `pass` (5 + 12)

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
zero. Restored by copy.

One correction to the finding as filed: the assertion is not order-dependent.
It runs in a fresh subprocess and always could fail for its stated reason -- it
was simply blind to two of the three modules that reason covers.

The generation half of this step is carried by the readmit and withdraw gates
added with S416, in `test_installed_generation_composition.py`, 10 passed.

Separately, the recovery-minting prohibition was red and its anchor was the
reason. `_MINTING_CALLABLES` named `generate_recovery_key` on the storage
PACKAGE; the import-centralisation work removed that re-export, so the anchor
could no longer resolve it. That is the anchor working exactly as designed --
it exists so a rename or a move reds the test instead of silently emptying the
prohibition -- and the fix is to name the canonical defining module,
`...storage.recovery_key`, which is also what the architecture rule requires of
every consumer. The prohibition scans for the symbol NAME, so it never depended
on where the definition lived.

Both halves re-proven. Importing the primitive into `home.py` fails the
prohibition with `Offenders: home.py:generate_recovery_key`; renaming the
anchored symbol fails the anchor with `module ... has no attribute`. Each file
restored by copy and the restore verified.

A third gate was stale rather than protective. `test_home_fixtures.py` pinned
the synthetic names `fixture.classify`, `fixture.review_blocker` and
`fixture.blocked_dependency`. Those ids and codes no longer exist: reason codes
and action ids are transport tokens keying `tui.home.reason.<code>`, and the
fixtures were deliberately moved onto the real `operator.*` ids and semantic
codes so their copy resolves through the catalogue. A `fixture.`-prefixed code
resolves to nothing and renders Home's degraded generic line, so the gate was
pinning the wrong thing AND failing for a reason unrelated to what it checked.

Both assertions now check the property instead of the name. The cross-cutting
action is found by the ABSENCE of an address, which is what Home actually has
to render alongside an addressed one. Every reason code must reach real copy,
read from the catalogue file rather than through `tr()` -- `tr()` humanises a
missing key into a plausible sentence, so a resolution check routed through it
can never observe the absence it exists to find.

Teeth proven on both halves: a code with no copy fails with
`'no_such_reason' has no copy, so Home degrades to its generic line`, and
giving every action an address fails the structural half. Restored by copy,
restores verified. Devtools then ran fully green: 157 passed.
