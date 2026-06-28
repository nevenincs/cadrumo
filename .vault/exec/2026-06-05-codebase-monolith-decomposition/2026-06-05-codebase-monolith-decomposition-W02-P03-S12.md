---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S12'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S12 - live notifications extraction

Scope: `src/aeat/entrypoints/cli/_app_live.py` and `src/aeat/entrypoints/cli/_app_live_notifications_cli.py`.

## Description

- Added `_app_live_notifications_cli.py` as the focused Typer registrar for live notification commands.
- Moved notification app creation, command bodies, output shaping, and service invocation out of `_app_live.py`.
- Replaced the removed `_app_live.py` command block with `register_notifications_commands(app, active_bucket_id=..., auth_preflight=...)`.
- Preserved `_app_live.py` as the top-level export facade for `notifications_app`.

## Outcome

`_app_live.py` no longer owns the notification command bodies. The new module consumes application-layer `capture_notifications` and `NotificationsService`, while the root injects the shared active-bucket resolver and live-auth preflight function.

## Notes

The new module uses ASCII fallback help text in defaults. Locale-backed text remains authoritative where translations are present.
