---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S06'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S06 - live slice selection

Scope: `src/aeat/entrypoints/cli/_app_live.py`.

## Description

- Ran exact discovery for Typer groups and commands in `_app_live.py`.
- Ran exact discovery for live notification, expediente, censo, and declaration test coverage.
- Ran semantic `vaultspec-rag` code search for live CLI command groups.
- Selected the notifications noun group as the first live extraction slice.

## Outcome

The selected slice covers:

```text
notifications_app
notifications_capture
notifications_list
notifications_show
notifications_latest
```

The group is backed by application-layer `capture_notifications` and `NotificationsService` calls. Dedicated real-behavior tests exist in `test_live_notifications_verbs.py`, and root command help coverage exists in `test_registry_cli.py`.

## Notes

RAG search succeeded through the running service and identified notifications plus expedientes command bodies. Notifications was selected first because it is a smaller, coherent subgroup with dedicated tests and limited helper coupling.
