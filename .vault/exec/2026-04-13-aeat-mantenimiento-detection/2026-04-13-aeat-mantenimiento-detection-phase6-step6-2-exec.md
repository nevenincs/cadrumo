---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase6-step6-2 cli health unit tests

## Intent

Parametrise the ADR-locked exit-code table through a real CLI
invocation using Typer's `CliRunner` with a test double that
implements the `HealthProbeLike` protocol and raises a real
`SiteHealthError` built from on-disk fixtures.

## Changes

- `src/aeat/entrypoints/cli/browser/test_health.py` — new `@pytest.mark.unit`
  module covering OK, mantenimiento, WAF, and rate-limit paths,
  plus a JSON-output payload assertion. `monkeypatch.setattr`
  replaces the module-level `PROBE_FACTORY` attribute; no
  `unittest.mock` usage.

## Deviations

None.
