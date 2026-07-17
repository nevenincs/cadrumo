---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S23'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add a plugin layout target that emits .claude-plugin/plugin.json with a kebab-case name, defaultEnabled false, an author object and the version read from installed package metadata

## Scope

- `src/aeat/agent/_workspace.py`

## Description

- Add a plugin layout target to `_workspace.py` emitting `.claude-plugin/plugin.json`.
- Set the manifest's `name` to the kebab-case `aeat` slug, `defaultEnabled` to `false`, and populate an `author` object.
- Read `version` from installed package metadata rather than a hardcoded literal.
- Declare the Apache-2.0 license on the manifest.
- Export the new target from `__init__.py`.
- Commit `ef183fb060`.

## Outcome

- The materialiser emits a schema-shaped `plugin.json` with `defaultEnabled: false` and a metadata-derived version.

## Notes

No incidents. No skipped work.
