---
tags:
  - '#exec'
  - '#just-tooling-bootstrap'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S02'
related:
  - '[[2026-06-04-just-tooling-bootstrap-plan]]'
---

# S02 Add Quality Audit Recipes

Scope: `justfile`.

## Description

- Add a strict `quality` recipe that composes the existing daily gates.
- Add advisory audit recipes for type improvement, structure, production dependency drift, dead code, deprecation, complexity, duplication, and security.
- Add `quality-audit` as a non-blocking dashboard recipe that invokes each advisory audit surface.

## Outcome

The `justfile` now exposes a modern quality-audit command surface for finding duplication, dead code, dependency drift, type-control gaps, deprecation signals, complexity hotspots, and structural issues.

## Notes

The security audit recipe prefers a workstation `semgrep` executable and falls back to `uvx --from semgrep semgrep`, which resolved successfully in this environment.
