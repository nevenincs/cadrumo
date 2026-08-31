---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:21be57c5e996781e923029bc423ccf3aa7a5573f8ec93ddfeb79f5f643546282'
step_id: 'S139'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Repoint the crash-recovery trace pin at the module that holds the delete effect, and teach the retirement sweep to read pins inside a subprocess source string

## Scope

- `src/cadrumo/application/tests/test_config_reset_recovery.py`
- `dev/quality/namespace_retirement_sweep.py`

## Changes

- `M` `src/cadrumo/application/tests/test_config_reset_recovery.py`
- `M` `dev/quality/namespace_retirement_sweep.py`
- `verify:` `pytest .../test_config_reset_recovery.py -n 0 -m ""` -> pass (15), was 2 failing
- `verify:` probe from the job scratch directory: embedded pin visible True, visible to the outer walk alone False, prose not re-walked

## Notes

Two failures in the crash-recovery suite, and they were not caused by the
retention change -- that was truth-tabled identical first. The gate traces for a
delete in a file ending _lifecycle.py and injects a crash there. A peer renamed
the module holding ProfileCapsuleLifecycle.delete from _lifecycle.py to
lifecycle.py, so the pin then matched only invoices/_lifecycle.py -- a module
with no delete in it at all. The boundary was never injected.

Worth being precise about what failed. The gate DID notice: its own RuntimeError
says the effect moved or was renamed and the boundary was silently never
injected, which is the anti-vacuity guard working. Without it the suite would
have gone green over a destructive path it had stopped exercising.

The retirement sweep should have caught the stale pin and reported clean. The
reason is worth keeping: the whole crash-injection program is passed to a child
interpreter as ONE STRING, so every pin in it is a constant of the child, and
ast.parse of the parent sees a single opaque blob. The parent walk found zero
.py constants in a file that is almost nothing but pins.

The sweep now re-walks any string constant that itself parses as Python. Most
strings are not Python and raise, which is the filter -- confirmed by probe: a
sentence merely MENTIONING a module name is not re-walked, so it yields no false
positive.
