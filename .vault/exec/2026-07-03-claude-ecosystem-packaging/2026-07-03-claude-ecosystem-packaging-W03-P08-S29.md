---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S29'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Extend the aeat app agent CLI with a plugin layout target option selecting the plugin materialisation over the workspace layout

## Scope

- `src/aeat/entrypoints/cli/_app_agent_workspace.py`

## Description

- Extend `_app_agent_workspace.py` with a `--layout plugin|workspace` Typer enum option selecting plugin materialisation over the existing workspace layout.
- Add the corresponding en/es/ca/hu locale keys through the locales CLI (`python -m aeat.locales set` / `scaffold`), never by hand-editing the catalogues.
- Commit `9d07e95585`.

## Outcome

- `python -m aeat.locales scaffold --check` clean at commit time.

## Notes

Committed after `S30` even though the plan lists `S29` first: the CLI option imports the payload/enum `S30` adds, so `S30` had to land first to keep collection green. No incidents. No skipped work.
