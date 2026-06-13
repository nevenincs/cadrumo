---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase6 summary - cli sub-app

Phase 6 landed `aeat browser health [--json]` as a directory-
backed sub-app. `health.py` opens a `BrowserSession`, calls
`navigate` against `settings.site_health_probe_url`, and prints a
human summary or a JSON dump of the `SiteHealthStatus`. Exit codes
match the ADR-locked table (0/2/3/4/5/6). A hidden `_reserved`
command exists on the sub-app to prevent Typer from collapsing the
single-command shape and breaking `aeat browser health`.

Unit tests use Typer's `CliRunner` and replace the module-level
`PROBE_FACTORY` attribute with a real test-double class that
raises real `SiteHealthError` instances built from on-disk
fixtures. No `unittest.mock` usage.

Steps: 6-1, 6-2.
