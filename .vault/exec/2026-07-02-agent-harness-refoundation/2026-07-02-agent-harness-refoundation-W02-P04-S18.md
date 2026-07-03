---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S18'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Update the workspace materialiser tests for the mirror layout

## Scope

- `src/aeat/agent/tests/test_workspace.py`

## Description

- Rewrite `src/aeat/agent/tests/test_workspace.py` for the Claude-native mirror layout over a real `tmp_path`.
- Assert the layout: `.claude/rules/<rule>.md`, `.claude/agents/<persona>.md`, `.claude/skills/<name>/SKILL.md` + `reference/casillas.md`, and a root `CLAUDE.md`.
- Assert the prior flat `rules/`, `personas/`, `skills/` directories are absent (no-legacy).
- Assert `CLAUDE.md` imports every operator rule via `@.claude/rules/<name>.md`.
- Assert strict byte-equality of written rules, personas, and a skill document against the shipped harness data.
- Assert manifest counts equal the files actually written per subtree.

## Outcome

6 tests pass; ruff and pyright clean. The mirror layout, its no-legacy replacement of the flat layout, the CLAUDE.md rule imports, and strict shipped-byte fidelity are all covered.

## Notes

Imported `materialise_workspace` directly from `.._workspace` (the module under test) rather than the `aeat.agent` package facade: the facade re-exports it via a lazy `__getattr__`, which pyright types as `object` ("not callable"). A test importing the implementation it exercises from its own package module is the idiomatic local-ownership pattern and keeps pyright clean; the `service-imports-via-top-level-reexports` rule governs cross-package production services, not same-package tests.
