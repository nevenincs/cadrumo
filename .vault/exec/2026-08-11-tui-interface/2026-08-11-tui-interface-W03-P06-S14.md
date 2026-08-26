---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a9148d8f0b7c277bc73d5ef7111f2d498a3528ef4ea98daa3d23c43d181a5e5c'
step_id: 'S14'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render explicit automatic-source capabilities scope authentication needs and operation launch actions

## Scope

- `src/cadrumo/entrypoints/tui/profile/overview.py`

## Changes

- `A` `src/cadrumo/application/user_profile/acquisition_sources.py`
- `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/profile/ -q -m "unit or integration"` -> `pass` (21 passed)

## Notes

"Capabilities scope and authentication needs" has no backing public contract today (no operation declares requires-auth/scope, and the existing CapabilityDecision resolver covers unrelated service opt-ins, not acquisition sources). Rendered only the explicit source identity and launch action; reported rather than fabricating a local policy.
