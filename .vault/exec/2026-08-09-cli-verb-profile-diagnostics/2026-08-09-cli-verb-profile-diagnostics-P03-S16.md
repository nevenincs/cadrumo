---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:905f92c5a0902cf325149e552fe04d7f53296e6e56eeed745060923e006f7d6b'
step_id: 'S16'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add real tests asserting the diagnostics profile-readiness check names its missing fields by label

## Scope

- `src/cadrumo/application/tests/test_diagnostics_profile_grounding.py`

## Description

- Added an anchor test asserting the probed field's operator label differs from its dotted path, so the label assertions cannot pass vacuously.
- Added a test asserting a known profile path renders with its operator label.
- Added a test asserting the rendered form keeps the path ahead of the separator, which the enrolment de-duplication depends on.
- Added a test asserting an unresolvable key is returned unchanged.

## Outcome

All four behaviours of the rendering are covered against the real committed schema, with no mocks or constructed schema needed, since the real schema expresses every case.

The de-duplication test is the one that earns its place. The rendering change is cosmetic in isolation, but it feeds a comparison a few lines above it that splits on the separator, so a plausible "cleaner" rewrite putting the label first would silently duplicate enrolment findings. That coupling is now asserted rather than left as a comment.

## Verification

    uv run --no-sync pytest src/cadrumo/application/tests/test_diagnostics_profile_grounding.py -n 0 -q
    4 passed in 2.36s

## Notes

The anchor test is deliberately about the fixture rather than about behaviour. Without it, a schema change making a label equal to its path would turn the two label assertions into no-ops that still report green.
