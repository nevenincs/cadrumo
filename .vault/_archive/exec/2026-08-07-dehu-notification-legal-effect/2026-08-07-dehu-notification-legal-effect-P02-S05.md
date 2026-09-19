---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6dd95af82335150cfc926061c168bb0ae644ec810bba9885a01bd9db72e98aea'
step_id: 'S05'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Add a new core module declaring the NotificacionEstadoServicio StrEnum, with members NO_ENTREGADA, ACCEDIDA, EN_PLAZO and RECHAZO_TACITO, and a pure function computing it from fecha_notificacion, leida and an explicit as_of date against DEHU_RECHAZO_TACITO_DIAS_NATURALES, then add boundary tests covering day 9 EN_PLAZO, day 10 RECHAZO_TACITO, fecha_notificacion is None NO_ENTREGADA, and leida is True ACCEDIDA regardless of elapsed days, plus a mutation-proof test that flips the day-10 boundary comparison and confirms the boundary test fails

## Scope

- `src/cadrumo/core/_notificacion_estado_servicio.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/core/tests/test_notificacion_estado_servicio.py`

## Description

- Declare the `NotificacionEstadoServicio` StrEnum in its own core module,
  following the established procedural-category module's shape: module
  docstring stating why the axis is orthogonal to the procedural one,
  per-member Attributes documentation, no I/O, no clock, explicit `__all__`.
- Add the pure resolver taking `fecha_notificacion`, `leida` and a required
  keyword-only `as_of`, comparing elapsed dias naturales against the pinned
  statutory constant rather than a literal.
- Promote both symbols onto the core package facade, since the consuming
  application and entrypoint packages resolve core symbols through it.
- Add the boundary suite plus an in-suite anti-tautology proof, and prove the
  suite bites by reverting the boundary comparison at runtime.

## Outcome

`src/cadrumo/core/_notificacion_estado_servicio.py` declares the four-member
axis and `resolve_notificacion_estado_servicio`. Both are exported from the
core facade and its `__all__`.

Two ordering decisions are documented at their sites rather than left implicit.
The undelivered guard is checked BEFORE the access flag, so a pendiente row
carrying a stray access value cannot report as served; and an `as_of` preceding
the puesta a disposicion yields the in-window state, because the window has not
opened rather than lapsed.

## Verification

    uv run --no-sync pytest src/cadrumo/core/tests/test_notificacion_estado_servicio.py -n0 -q
    16 passed in 1.37s

Mutation proof, run with a plugin loaded from OUTSIDE the repository so no
tracked file was edited. The mutation is the plausible off-by-one: the window
comparison becomes strictly-greater, deferring deemed service by one day, which
is the understate-urgency direction.

    PYTHONPATH=<scratchpad> uv run --no-sync pytest src/cadrumo/core/tests/test_notificacion_estado_servicio.py -n0 -q -s -p mutate_dehu_boundary
    MUTATION APPLIED to 3 holder(s): ['cadrumo.core', 'cadrumo.core._notificacion_estado_servicio', 'cadrumo.core.tests.test_notificacion_estado_servicio']
    3 failed, 13 passed in 3.59s

The plugin refuses with an explicit no-op error when no module holds the target
name, so a green run cannot mean the rebinding silently found nothing. Three
holders were rebound and the two day-ten assertions plus the anti-tautology
proof went red, while every other boundary case stayed green.

    uv run --no-sync ruff check src/cadrumo/core/_notificacion_estado_servicio.py src/cadrumo/core/tests/test_notificacion_estado_servicio.py src/cadrumo/core/__init__.py
    All checks passed!

    uv run --no-sync python -m dev.docs.apidocs scaffold --check
    Stub tree is conformant. No drift detected.

## Notes

The module, its tests and the facade edits were swept into an unrelated peer
commit ("land the in-flight source work") by a bare whole-index commit before
this Step could commit them itself. The content is intact in the tree; the
import-ordering violation that went in with the sweep was corrected and
committed separately alongside the generated API stubs. Nothing was lost and
nothing needed re-authoring, but the sweep is why this Step's content spans two
commits, only one of which carries a subject naming it.
