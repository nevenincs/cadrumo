---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase6-step6-1 cli browser health sub-app

## Intent

Land a directory-backed `aeat browser` sub-app exposing
`aeat browser health [--json]` with the ADR-locked exit-code table.

## Changes

- `src/aeat/entrypoints/cli/browser/__init__.py` — new sub-app wiring.
- `src/aeat/entrypoints/cli/browser/health.py` — command implementation. Uses a
  module-level `PROBE_FACTORY` callable as the sanctioned
  dependency-injection seam so unit tests can inject a concrete
  test double without `unittest.mock`. The default factory imports
  Playwright and builds a real `BrowserSession`; imports are
  lazy-loaded inside the factory to keep test startup Playwright-
  free.
- `src/aeat/entrypoints/cli/__init__.py` — `app.add_typer(browser_module.app,
  name="browser", ...)`.

## Exit-code table

0: OK, 2: MANTENIMIENTO, 3: WAF_CHALLENGE, 4: RATE_LIMITED,
5: UNREACHABLE, 6: UNKNOWN_ERROR.

## Deviations

The plan suggested a `--session-factory` typer option. Using a
typer option would force the injected factory to be importable via
a module path string, which is less ergonomic than replacing a
module-level callable directly. The module-level `PROBE_FACTORY`
attribute approach is documented in-source and explicitly called
out as the sanctioned DI seam.
